package org.renci.babel.utils.validator

import com.typesafe.scalalogging.LazyLogging
import org.renci.babel.utils.cli.Utils.SupportsFilenameFiltering
import org.renci.babel.utils.model.{BabelOutput, Compendium}
import org.rogach.scallop.{ScallopOption, Subcommand}
import zio.ZIO
import zio.blocking.Blocking
import zio.console.Console
import zio.json._
import zio.stream.ZStream

import java.io.{File, FileWriter, PrintWriter}
import scala.collection.Set

/**
 * Validate Babel outputs.
 */
object Validator extends LazyLogging {
  val DEFAULT_CORES = 5;

  val EXPECTED_COMPENDIA: Set[String] = Set(
    "AnatomicalEntity.txt",
    "Disease.txt",
    "OrganismTaxon.txt",
    "BiologicalProcess.txt",
    "GeneFamily.txt",
    "Pathway.txt",
    "Cell.txt",
    "Gene.txt",
    "PhenotypicFeature.txt",
    "CellularComponent.txt",
    "GrossAnatomicalStructure.txt",
    "Polypeptide.txt",
    "ChemicalEntity.txt",
    "MacromolecularComplexMixin.txt",
    "Protein.txt",
    "ChemicalMixture.txt",
    "MolecularActivity.txt",
    "SmallMolecule.txt",
    "ComplexMolecularMixture.txt",
    "MolecularMixture.txt",
    "umls.txt"
  )
  val EXPECTED_SYNONYMS: Set[String] = Set(
    "AnatomicalEntity.txt",
    "Disease.txt",
    "OrganismTaxon.txt",
    "BiologicalProcess.txt",
    "GeneFamily.txt",
    "Pathway.txt",
    "Cell.txt",
    "Gene.txt",
    "PhenotypicFeature.txt",
    "CellularComponent.txt",
    "GrossAnatomicalStructure.txt",
    "Polypeptide.txt",
    "ChemicalEntity.txt",
    "MacromolecularComplexMixin.txt",
    "Protein.txt",
    "ChemicalMixture.txt",
    "MolecularActivity.txt",
    "SmallMolecule.txt",
    "ComplexMolecularMixture.txt",
    "MolecularMixture.txt",
    "umls.txt"
  )
  val EXPECTED_CONFLATIONS: Set[String] = Set(
    "GeneProtein.txt"
  )

  /** The subcommand that controlling converting. */
  class ValidateSubcommand
      extends Subcommand("validate")
      with SupportsFilenameFiltering {
    val babelOutput: ScallopOption[File] = trailArg[File](
      descr = "The current Babel output directory",
      required = true
    )
    validateFileIsDirectory(babelOutput)

    val nCores: ScallopOption[Int] =
      opt[Int](descr = "Number of cores to use", default = Some(DEFAULT_CORES))

    val output: ScallopOption[File] =
      opt[File](descr = "Output directory", required = true)
    validateFileDoesNotExist(output)
  }

  def validate(
      conf: ValidateSubcommand
  ): ZIO[Blocking with Console, Throwable, Unit] = {
    val babelOutput = new BabelOutput(conf.babelOutput())
    val outputDir = conf.output()

    // Create directories for compendia and synonym reports.
    val outputCompendia = new File(outputDir, "compendia")
    outputCompendia.mkdirs()

    val outputSynonyms = new File(outputDir, "synonyms")
    outputSynonyms.mkdirs()

    val outputConflations = new File(outputDir, "conflation")
    outputConflations.mkdirs()

    // Start writing out an overall output file.
    zio.blocking
      .effectBlockingIO(
        new PrintWriter(new FileWriter(new File(outputDir, "validation.txt")))
      )
      .bracketAuto { pw =>
        for {
          compendiumSummaries <- ZIO.succeed(Seq[CompendiumSummary]()) // validateCompendia(pw, babelOutput)
          synonymNames <- validateSynonyms(pw, babelOutput)
          conflationNames <- validateConflations(pw, babelOutput)
        } yield {
          val successfulCompendia = compendiumSummaries.filter(_.valid)
          val failedCompendia = compendiumSummaries.filter(!_.valid)

          logger.info(
            s"Validated ${successfulCompendia.size} compendia: [${successfulCompendia.map(_.compendium.filename).mkString(", ")}]"
          )
          if (failedCompendia.nonEmpty)
            logger.info(
              s"${failedCompendia.size} compendia failed validation: [${failedCompendia
                  .map(_.compendium.filename)
                  .mkString(", ")}]"
            )
          logger.info(
            s"Validated synonyms [${synonymNames.size}]: ${synonymNames}"
          )
          logger.info(
            s"Validated conflations [${conflationNames.size}]: ${conflationNames}"
          )
        }
      }
  }

  case class CompendiumSummary(
      compendium: Compendium,
      valid: Boolean,
      types: Set[String],
      prefixes: Map[String, Int]
  )

  def validateCompendia(
      pw: PrintWriter,
      output: BabelOutput
  ): ZIO[Blocking with Console, Throwable, Seq[CompendiumSummary]] = {
    val compendia = output.compendia
    val compendiaFilenames = compendia.map(_.filename).toSet
    if (compendiaFilenames != EXPECTED_COMPENDIA) {
      val errorStr =
        s"""FAIL: compendia missing
            | - Expected: ${EXPECTED_COMPENDIA}
            | - Observed: ${compendiaFilenames}
            |   - Extra files: ${compendiaFilenames.diff(EXPECTED_COMPENDIA)}
            |   - Missing files: ${EXPECTED_COMPENDIA.diff(
            compendiaFilenames
          )}""".stripMargin
      logger.error(errorStr)
      pw.println(errorStr)
      pw.flush()
    }

    ZStream
      .fromIterable(compendia)
      .map(compendium => {
        val resultsZS = for {
          record <- compendium.records

          // Type
          typ = record.`type`

          // We define the prefix as everything until the LAST ':'. This allows us to check for CHEBI:CHEBI: bugs
          // (see https://github.com/TranslatorSRI/babel-validation/issues/16)
          prefixes = record.identifiers
            .map(_.i)
            .map(identifierOpt => {
              val identifier = identifierOpt.getOrElse("(no identifier)")
              val prefixComponents = identifier.split(':')
              prefixComponents.tail.mkString(":")
            })
        } yield (typ, prefixes)

        val results = zio.Runtime.default.unsafeRun(resultsZS.runCollect)
        val valid = {
          if (results.isEmpty) {
            val errorStr =
              s"FAIL: compendium ${compendium.filename} has zero records."
            logger.error(errorStr)
            pw.println(errorStr)
            pw.flush()
            false
          } else {
            val successStr =
              s"SUCCESS: compendium $compendium passed validation with ${results.size} records."
            logger.info(successStr)
            pw.println(successStr)
            pw.flush()
            true
          }
        }

        CompendiumSummary(
          compendium,
          valid,
          results.map(_._1).toSet,
          results.flatMap(_._2.groupBy(identity)).toMap.mapValues(_.size).toMap
        )
      })
      .runCollect
  }

  case class SynonymSummary(
      filename: String,
      synonymCount: Long
  )

  def validateSynonyms(
      pw: PrintWriter,
      output: BabelOutput
  ): ZIO[Blocking with Console, Throwable, Seq[SynonymSummary]] = {
    val synonyms = output.synonyms
    if (synonyms.keySet != EXPECTED_SYNONYMS) {
      pw.println(
        s"FAIL: synonyms missing\n- Expected: ${EXPECTED_SYNONYMS}\n- Observed: ${synonyms.toSet}"
      )
      ZIO.succeed(Seq());
    } else {
      for {
        summaries <- ZStream
          .fromIterable(synonyms)
          .flatMap({
            case (filename, synonyms) => ZStream.fromEffect(synonyms.synonyms.map(_.synonym).runCount)
              .map(count => SynonymSummary(filename, count))
          })
      } yield summaries
    }.runCollect
  }

  case class ConflationSummary(
      filename: String,
      sourceIds: Set[String],
      destIds: Set[String],
      relations: Set[String]
  )

  def validateConflations(
      pw: PrintWriter,
      output: BabelOutput
  ): ZIO[Blocking with Console, Throwable, Seq[String]] = {
    val conflations = output.conflations
    if (conflations.toSet != EXPECTED_CONFLATIONS) {
      pw.println(
        s"FAIL: conflations missing\n- Expected: ${EXPECTED_CONFLATIONS}\n- Observed: ${conflations.toSet}"
      )
      ZIO.succeed(Seq());
    } else {
      ZStream
        .fromIterable(conflations)
        .map(conflation => {

          conflation
        })
        .runCollect
    }
  }
}
