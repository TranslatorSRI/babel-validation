package org.renci.babel.utils.cli

import com.typesafe.scalalogging.LazyLogging
import Utils.SupportsFilenameFiltering
import org.renci.babel.utils.model.{BabelOutput, Compendium}
import org.rogach.scallop.{ScallopOption, Subcommand}
import zio.ZIO
import zio.blocking.Blocking
import zio.console.Console
import zio.stream.{ZSink, ZStream}

import java.io.{File, FileOutputStream, PrintStream}
import java.io.{File, FileOutputStream, OutputStreamWriter}
import java.time.LocalDateTime

/**
 * Functions for reporting on the differences between two input files.
 */
object DiffReporter extends LazyLogging {
  /** The subcommand that controlling comparing. */
  class DiffSubcommand extends Subcommand("diff") with SupportsFilenameFiltering {
    val babelOutput: ScallopOption[File] = trailArg[File](
      descr = "The current Babel output directory",
      required = true
    )
    val babelPrevOutput: ScallopOption[File] =
      trailArg[File](descr = "The previous Babel output", required = true)
    validateFileIsDirectory(babelOutput)
    validateFileIsDirectory(babelPrevOutput)

    val nCores: ScallopOption[Int] = opt[Int](descr = "Number of cores to use")

    val output: ScallopOption[File] = opt[File](descr = "Output file")
  }

  /**
   * Given two BabelOutputs, it returns a list of all compendia found in BOTH of the BabelOutputs
   * paired together.
   *
   * TODO: modify this so we return every compendium found in EITHER BabelOutput.
   */
  def retrievePairedCompendiaSummaries(
      babelOutput: BabelOutput,
      babelPrevOutput: BabelOutput
  ): Seq[(String, Compendium, Compendium)] = {
    for {
      summary <- babelOutput.compendia
      summaryPrev <- babelPrevOutput.compendia
      if summaryPrev.filename == summary.filename
    } yield {
      (summary.filename, summary, summaryPrev)
    }
  }

  def diffResults(conf: DiffSubcommand): ZIO[Blocking with Console, Throwable, Unit] = {
    val babelOutput = new BabelOutput(conf.babelOutput())
    val babelPrevOutput = new BabelOutput(conf.babelPrevOutput())
    val outputDir = conf.output.getOrElse(new File("."))

    val summaryFile = new File(outputDir, "diff-summary.txt")

    val pairedSummaries =
      retrievePairedCompendiaSummaries(babelOutput, babelPrevOutput)
    // output.println("Filename\tCount\tPrevCount\tDiff\tPercentageChange")
    ZStream
      .fromIterable(pairedSummaries)
      .mapMPar(conf.nCores()) {
        case (
          filename: String,
          summary: Compendium,
          prevSummary: Compendium
          ) if Utils.filterFilename(conf, filename) => {

          for {
            // lengthComparison <- Comparer.compareLengths(filename, summary, prevSummary)
            // typeComparison <- Comparer.compareTypes(filename, summary, prevSummary)
            clusterComparison <- Comparer.diffClustersByIDs(
              filename,
              summary,
              prevSummary,
              conf.nCores()
            )
          } yield {
            // output.println(lengthComparison.toString)
            // output.println(typeComparison.toString)
            val basename = filename

            val osw = new OutputStreamWriter(
              new FileOutputStream(new File(outputDir, basename))
            )
            clusterComparison.writeToFile(osw)
            osw.close()

            logger.info(
              f"Wrote ${clusterComparison.comparisons.size}%,d comparisons to ${filename}."
            )

            val summary =
              s"== ${filename} ==\n" + clusterComparison.countsByStatus + "\n\n"
            logger.info(summary)

            summary
          }
        }
        case (filename: String, _, _) if !Utils.filterFilename(conf, filename) => {
          logger.info(s"Skipping ${filename}")
          ZIO.succeed("")
        }
        case abc =>
          ZIO.fail(new RuntimeException(s"Invalid paired summary: ${abc}"))
      }
      .run(
        ZSink
          .fromFile(summaryFile.toPath)
          .contramapChunks[String](_.flatMap(_.getBytes))
      ) // Returns the number of written bytes as a Long
      .unit // Ignore the number of written bytes
      .andThen(ZIO.effect({
        // Report that the diff has completed.
        logger.info(s"Diff completed at ${LocalDateTime.now()}")
      }))
  }
}
