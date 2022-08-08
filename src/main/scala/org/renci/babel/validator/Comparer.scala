package org.renci.babel.validator

import com.typesafe.scalalogging.LazyLogging
import org.renci.babel.utils.MemoryUtils
import org.renci.babel.validator.model.Compendium
import zio.blocking.Blocking
import zio.stream.ZStream
import zio.{Chunk, ZIO}

import java.io.Writer

/** Methods in this class can be used to compare results between two compendia.
  */
object Comparer extends LazyLogging {

  /** Helper method for displaying the percent change between two counts.
    */
  def relativePercentChange(count: Long, countPrev: Long): String = {
    val percentChange = (count - countPrev).toDouble / countPrev * 100
    f"${count - countPrev}%+d\t$percentChange%+2.2f%%"
  }

  case class LengthComparison(filename: String, count: Long, prevCount: Long) {
    val relativePercentChange: String =
      Comparer.relativePercentChange(count, prevCount)
    override val toString: String =
      s"${filename}\t${count}\t${prevCount}\t${relativePercentChange}"
  }

  def compareLengths(
      filename: String,
      summary: Compendium,
      prevSummary: Compendium
  ): ZIO[Blocking, Throwable, LengthComparison] = {
    for {
      count <- summary.count
      prevCount <- prevSummary.count
    } yield LengthComparison(filename, count, prevCount)
  }

  case class TypeComparison(
      filename: String,
      types: Chunk[String],
      prevTypes: Chunk[String]
  ) {
    val typesSet = types.toSet
    val prevTypesSet = types.toSet
    val added: Set[String] = typesSet -- prevTypesSet
    val deleted: Set[String] = prevTypesSet -- typesSet
    val changeString: String = (added.toSeq, deleted.toSeq) match {
      case (Seq(), Seq())   => "No change"
      case (added, Seq())   => s"Added: ${added}"
      case (Seq(), deleted) => s"Deleted: ${deleted}"
      case (added, deleted) =>
        s"Added: ${added}, Deleted: ${deleted}"
    }

    override val toString: String =
      s"${filename}\t${typesSet.mkString(", ")} (${types.length})\t${prevTypesSet
          .mkString(", ")} (${prevTypes.length})\t${changeString}"
  }

  def compareTypes(
      filename: String,
      summary: Compendium,
      prevSummary: Compendium
  ): ZIO[Blocking, Throwable, TypeComparison] = {
    for {
      typesChunk <- (for {
        row: Compendium.Record <- summary.records
      } yield (row.`type`)).runCollect
      typesErrors <- summary.types.catchAll(err => {
        logger.error(s"Types error: ${err}")
        ZIO.fail(err)
      })
      prevTypesChunk <- (for {
        row: Compendium.Record <- prevSummary.records
      } yield (row.`type`)).runCollect
      prevTypesErrors <- prevSummary.types.catchAll(err => {
        logger.error(s"prevTypes error: ${err}")
        ZIO.fail(err)
      })
    } yield {
      TypeComparison(filename, typesChunk, prevTypesChunk)
    }
  }

  case class ClusterComparison(
      id: String,
      records: Set[Compendium.Record],
      prevRecords: Set[Compendium.Record]
  ) {
    val unchanged: Boolean = (records == prevRecords)
    val status: String = {
      if (records.isEmpty && prevRecords.isEmpty) "ERROR_BLANK"
      else if (unchanged) "UNCHANGED"
      else if (records.isEmpty && prevRecords.nonEmpty) "DELETED"
      else if (records.nonEmpty && prevRecords.isEmpty) "ADDED"
      else {
        // The records have changed, but how? Changes in which only the labels have changed are less "severe"
        // than ones in which identifiers have changed, so let's try to separate those.
        val identifiers = records.flatMap(_.identifiers).map(_.i).toSeq.sorted
        val prevIdentifiers =
          prevRecords.flatMap(_.identifiers).map(_.i).toSeq.sorted
        val overlapIdentifiers =
          identifiers.flatten.intersect(prevIdentifiers.flatten)

        if (identifiers == prevIdentifiers) "CHANGED_BUT_IDENTIFIERS_IDENTICAL"
        else if (overlapIdentifiers.nonEmpty) "CHANGED_BUT_SHARED_IDENTIFIERS"
        else "CHANGED"
      }
    }
    override val toString: String = if (unchanged) {
      s"${id}\t${status}\t${records.size}\t${prevRecords.size}"
    } else {
      def multilineRecords(s: Set[Compendium.Record], indent: Int = 2): String =
        if (s.isEmpty) "Set()"
        else {
          val indentedStr = " " * indent

          "Set(\n" +
            s.map(indentedStr + "  " + _.toString).mkString(", \n") +
            "\n" + indentedStr + ")"
        }
      s"${id}\t${status}\t${multilineRecords(prevRecords)} [${prevRecords.size}]\t->\t${multilineRecords(records)} [${records.size}]"
    }
  }

  case class ClusterComparisonReport(
      filename: String,
      comparisons: Set[ClusterComparison]
  ) {
    override val toString: String = {
      s"${filename}: " + countsByStatus
    }

    def countsByStatus: String = {
      comparisons.toSeq
        .map(_.status)
        .groupBy(identity)
        .map[(Int, String)]({ case (status, values) =>
          (
            values.size,
            f"${status}: ${values.size} (${values.size.toDouble / comparisons.size * 100}%.4f%%)"
          )
        })
        .toSeq
        .sortBy(-_._1)
        .map(_._2)
        .mkString("\n")
    }

    def writeToFile(w: Writer): Unit = {
      w.write(s"== ${filename} ==\n")
      w.write(countsByStatus + "\n")

      comparisons
        .filterNot(_.unchanged)
        .groupBy(_.status)
        .foreach({ case (status, clusterComparisons) =>
          w.write(s"\n=== ${status} [${clusterComparisons.size}] ===\n")
          clusterComparisons.foreach(c => w.write(s" - ${c.toString}\n"))
        })
    }
  }

  /** Given two compendia, generate the "diff" between clusters in the two
    * compendia based on the individual identifiers. For every identifier
    * mentioned in either compendium, we identify the clusters it is included in
    * in both the current compendium and the previous compendium. For most
    * identifiers, we would expect these clusters to be unchanged, so this
    * approach allows us to focus on the clusters that _have_ changed.
    *
    * The downside to this approach is that we generate more "diffs" than have
    * actually taken place: for instance, if identifier 1 is added to cluster 1
    * containing a single identifier 2, this results in two diffs: identifier 1
    * was ADDED to cluster 1, but identifier 2 was MODIFIED. In the future, it
    * might be worth summarizing these diffs further.
    *
    * @param filename
    *   The name of the compendium begin compare.
    * @param compendium
    *   The current compendium.
    * @param prevCompendium
    *   The previous compendium.
    * @param nCores
    *   The number of cores available for this task.
    * @return
    *   A ZIO that evaluates to a ClusterComparisonReport or a Throwable.
    */
  def diffClustersByIDs(
      filename: String,
      compendium: Compendium,
      prevCompendium: Compendium,
      nCores: Int
  ): ZIO[Blocking, Throwable, ClusterComparisonReport] = {
    // Not sure what a good limit should be for this, but so far we haven't hit a memory limit on HashSet.
    val IDENTIFIER_ZSTREAM_LIMIT = 999_999_999

    val runtime = zio.Runtime.default
    val identifiersZIO = (compendium.records.map(
      _.ids
    ) ++ prevCompendium.records.map(_.ids)).runCollect
      .map(_.foldLeft(Set[String]())(_ ++ _))

    val identifiers = runtime.unsafeRun(identifiersZIO)

    logger.info(
      f"Found ${identifiers.size}%,d identifiers for filename ${filename}"
    )

    if (identifiers.size < IDENTIFIER_ZSTREAM_LIMIT) {
      // If the number of identifiers is small enough, then don't both to use the ZStream algorithm --
      // just use a HashSet and assume it'll fit in memory.
      logger.info(
        f"Memory at start of identifier process: ${MemoryUtils.getMemorySummary}"
      )
      val records = runtime.unsafeRun(compendium.records.runCollect).toList
      logger.debug(f"  Loaded records: ${MemoryUtils.getMemorySummary}")
      val prevRecords =
        runtime.unsafeRun(prevCompendium.records.runCollect).toList
      logger.debug(f"  Loaded prevRecords: ${MemoryUtils.getMemorySummary}")
      val summary =
        records.flatMap(r => r.ids.map(id => (id, r))).groupMap(_._1)(_._2)
      logger.debug(f"  Generated summary: ${MemoryUtils.getMemorySummary}")
      val prevSummary =
        prevRecords.flatMap(r => r.ids.map(id => (id, r))).groupMap(_._1)(_._2)
      logger.debug(f"  Generated prevSummary: ${MemoryUtils.getMemorySummary}")

      val comparisons = identifiers.map(id => {
        ClusterComparison(
          id,
          summary.getOrElse(id, List()).toSet,
          prevSummary.getOrElse(id, List()).toSet
        )
      })

      logger.info(
        f"Memory at end of cluster comparison generation: ${MemoryUtils.getMemorySummary}"
      )

      return ZIO.succeed(ClusterComparisonReport(filename, comparisons))
    }

    for {
      identifiers <- identifiersZIO

      // If identifiers < IDENTIFIER_ZSTREAM_LIMIT, we'll opt to just use a Set()
      // instead of the ZStream algorithm.
      summaryByCluster: ZStream.GroupBy[
        Blocking,
        Throwable,
        String,
        Compendium.Record
      ] = compendium.records
        .flatMap(record =>
          ZStream.fromIterable(record.ids).map(id => (id, record))
        )
        .groupBy({ case (id: String, record: Compendium.Record) =>
          ZIO.succeed((id, record))
        })
      prevSummaryByCluster: ZStream.GroupBy[
        Blocking,
        Throwable,
        String,
        Compendium.Record
      ] = prevCompendium.records
        .flatMap(record =>
          ZStream.fromIterable(record.ids).map(id => (id, record))
        )
        .groupBy({ case (id: String, record: Compendium.Record) =>
          ZIO.succeed((id, record))
        })
      comparisons = ZIO.foreachParN(nCores)(identifiers.toSeq)(id => {
        for {
          records <- summaryByCluster
            .filter(_ == id) { case (_, records) => records }
            .runCollect
          prevRecords <- prevSummaryByCluster
            .filter(_ == id) { case (_, records) => records }
            .runCollect
        } yield {
          // logger.info(s"ClusterComparison(${id}, ${records}, ${prevRecords})")
          ClusterComparison(id, records.toSet, prevRecords.toSet)
        }
      })
      comparison <- comparisons
    } yield {
      logger.info(
        f"Memory at end of ZStream identifier process: ${MemoryUtils.getMemorySummary}"
      )
      ClusterComparisonReport(filename, comparison.toSet)
    }
  }
}
