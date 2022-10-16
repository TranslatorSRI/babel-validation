package org.renci.babel.utils.converter

import com.typesafe.scalalogging.LazyLogging
import org.renci.babel.utils.cli.Utils.{SupportsFilenameFiltering, filterFilename}
import org.renci.babel.utils.model.{BabelOutput, Compendium, Synonym, Synonyms}
import org.rogach.scallop.{ScallopOption, Subcommand}
import zio.ZIO
import zio.blocking.Blocking
import zio.console.Console
import zio.json._
import zio.stream.{ZSink, ZStream}

import java.io.File

/**
 * Convert Babel files into other formats.
 */
object Converter extends LazyLogging {
  val DEFAULT_CORES = 5;

  /** The subcommand that controlling converting. */
  class ConvertSubcommand
      extends Subcommand("convert")
      with SupportsFilenameFiltering {
    val babelOutput: ScallopOption[File] = trailArg[File](
      descr = "The current Babel output directory",
      required = true
    )
    validateFileIsDirectory(babelOutput)

    val format: ScallopOption[String] = choice(
      choices = Seq(
        "sssom",
        "sapbert"
      ),
      descr = "The format to convert this Babel output to",
      default = Some("sssom")
    )

    val nCores: ScallopOption[Int] =
      opt[Int](descr = "Number of cores to use", default = Some(DEFAULT_CORES))

    val output: ScallopOption[File] =
      opt[File](descr = "Output directory", required = true)
    validateFileIsDirectory(output)
  }

  def convert(
      conf: ConvertSubcommand
  ): ZIO[Blocking with Console, Throwable, Unit] = {
    val babelOutput = new BabelOutput(conf.babelOutput())
    val outputDir = conf.output()

    val outputCompendia = new File(outputDir, "compendia")
    if (!outputCompendia.exists()) {
      outputCompendia.mkdirs()
    }

    val extension = conf.format() match {
      case "sssom"   => ".sssom.tsv"
      case "sapbert" => ".txt"
      case format    => throw new RuntimeException(s"Unknown format: ${format}")
    }

    ZIO
      .foreach(babelOutput.compendia) { compendium =>
        if (!filterFilename(conf, compendium.filename)) {
          logger.warn(
            s"Skipping ${compendium.filename} because of filtering options."
          )
          ZIO.succeed(())
        } else {
          val outputFilename =
            compendium.filename.replaceFirst("\\.\\w{1,3}$", extension)
          val outputFile = new File(outputCompendia, outputFilename)

          // Do we have a corresponding synonym file?
          val synonyms = babelOutput.synonyms.get(compendium.filename)

          conf.format() match {
            case "sssom" =>
              convertCompendiumToSSSOM(conf, compendium, outputFile)
            case "sapbert" =>
              convertCompendiumToSapbert(conf, compendium, synonyms, outputFile)
          }
        }
      }
      // TODO: we return a Long here of the number of bytes (lines?) written out, so reporting them to STDERR would be nice.
      .andThen(ZIO.succeed(()))
  }

  def convertCompendiumToSapbert(
      conf: ConvertSubcommand,
      compendium: Compendium,
      synonyms: Option[Synonyms],
      outputFile: File
  ): ZIO[Blocking with Console, Throwable, Long] = {
    // SAPBert uses a simple format:
    //  id||label||synonym
    val synonymsAsZIOOpt = synonyms.map(_.synonymsById)
    val synonymsById: Map[String, Seq[Synonym]] = synonymsAsZIOOpt match {
      case None => {
        logger.warn(s"No synonyms file found for compendium ${compendium} or file is empty.")
        Map()
      }
      case Some(synonymsByZIO) => zio.Runtime.default.unsafeRun(synonymsByZIO)
    }

    compendium.records.flatMapPar(conf.nCores.getOrElse(DEFAULT_CORES))(record => {
      // For this, we should only need to use the primary ID, but hey, while we're here, let's try all the identifiers.
      val synonymsForId = record.identifiers
        .filter(!_.i.isEmpty)
        .flatMap(id => synonymsById.get(id.i.get))
        .flatten

      // For SAPBert training, retrieve:
      // - the labels for this record
      // - all known synonyms for this record
      val namesForId = record.identifiers.flatMap(_.l) ++ (synonymsForId match {
        case Seq() => {
          // logger.debug(s"No synonyms found for clique ${record} in compendium ${compendium}")
          Seq()
        }
        case synonyms: Seq[Synonym] => synonyms.map(_.synonym)
      })
      val uniqueNamesForId = namesForId.toSet

      if (uniqueNamesForId.isEmpty) {
        // logger.warn(s"No names found for clique ${record} in compendium ${compendium}")
      }

      val labels = record.identifiers.flatMap(_.l)
      val primaryLabel = labels.headOption

      ZStream.fromIterable(uniqueNamesForId)
        .map(name => s"${record.primaryId.getOrElse("")}||${primaryLabel.getOrElse("")}||${name}")
    }).intersperse("\n")
      .run({
        logger.info(s"Writing to $outputFile")
        ZSink
          .fromFile(outputFile.toPath)
          .contramapChunks[String](_.flatMap(_.getBytes))
      })
  }

  def convertCompendiumToSSSOM(
      conf: ConvertSubcommand,
      compendium: Compendium,
      outputFile: File
  ): ZIO[Blocking, Throwable, Long] = {
    case class Other(
        cliqueId: String,
        subject_information_content: Option[Double],
        identifierIndex: Option[Long] = None
    )
    implicit val otherEncoder: JsonEncoder[Other] =
      DeriveJsonEncoder.gen[Other]

    val results = compendium.records.zipWithIndex
      .flatMapPar(conf.nCores.getOrElse(DEFAULT_CORES)) { case (record, cliqueIndex) =>
        val cliqueLeader = record.identifiers.head
        val otherIdentifiers = record.identifiers.tail

        logger.debug(s"Record: ${record}")
        logger.debug(s" - Clique leader: ${cliqueLeader}")
        logger.debug(s" - Others: ${otherIdentifiers}")

        val predicateId = "skos:exactMatch"
        val subjectString = s"${cliqueLeader.i.getOrElse("")}\t${cliqueLeader.l
            .getOrElse("")}\t${record.`type`}"

        // TODO: replace with mappingJustification => semapv:MappingChaining for the next version of SSSOM.
        val matchType = "HumanCurated"

        // TODO: remove tabs from other.toJson
        if (otherIdentifiers.isEmpty) {
          val other = Other(
            cliqueId = s"${compendium.filename}#$cliqueIndex",
            subject_information_content = record.ic
          )

          ZStream.fromIterable(
            Seq(
              // s"${subjectString}\t\t\t${matchType}\t${other.toJson}"
              s"$subjectString\t$predicateId\t$subjectString\t$matchType\t${other.toJson}"
            )
          )
        } else {
          ZStream
            .fromIterable(otherIdentifiers)
            .zipWithIndex
            .map({ case (obj, identifierIndex) =>
              val other = Other(
                cliqueId = s"${compendium.filename}#$cliqueIndex",
                subject_information_content = record.ic,
                identifierIndex = Some(identifierIndex)
              )

              val objectString =
                s"${obj.i.getOrElse("")}\t${obj.l.getOrElse("")}\t${record.`type`}"
              s"$subjectString\t$predicateId\t$objectString\t$matchType\t${other.toJson}"
            })
        }
      }

    (ZStream.fromIterable(
      Seq(
        s"subject_id\tsubject_label\tsubject_category\tpredicate_id\tobject_id\tobject_label\tobject_category\tmatch_type\tother"
      )
    ) concat results)
      .intersperse("\n")
      .run({
        logger.info(s"Writing to $outputFile")
        ZSink
          .fromFile(outputFile.toPath)
          .contramapChunks[String](_.flatMap(_.getBytes))
      })
  }
}
