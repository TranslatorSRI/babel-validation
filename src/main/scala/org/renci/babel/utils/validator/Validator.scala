package org.renci.babel.utils.validator

import com.typesafe.scalalogging.LazyLogging
import org.renci.babel.utils.cli.Utils.SupportsFilenameFiltering
import org.renci.babel.utils.model.BabelOutput
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

  val EXPECTED_COMPENDIA = Set(
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
  val EXPECTED_SYNONYMS = Set(
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
  val EXPECTED_CONFLATIONS = Set(
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

    val outputSynonyms = new File(outputDir, "conflation")
    outputSynonyms.mkdirs()

    // Start writing out an overall output file.
    zio.blocking.effectBlockingIO(new PrintWriter(new FileWriter(new File(outputDir, "validation.txt"))))
      .bracketAuto { pw =>
        for {
          compendiumNames <- validateCompendia(pw, babelOutput)
          synonymNames <- validateSynonyms(pw, babelOutput)
          conflationNames <- validateConflations(pw, babelOutput)
        } yield {
          logger.info(s"Validated compendia [${compendiumNames.size}]: ${compendiumNames}")
          logger.info(s"Validated synonyms [${synonymNames.size}]: ${synonymNames}")
          logger.info(s"Validated conflation [${conflationNames.size}]: ${conflationNames}")
        }
      }
  }

  def validateCompendia(pw: PrintWriter, output: BabelOutput): ZIO[Blocking with Console, Throwable, Seq[String]] = {
    val compendia = output.compendia
    if (compendia.toSet != EXPECTED_COMPENDIA) {
      pw.println(s"ERROR: compendia missing\n- Expected: ${EXPECTED_COMPENDIA}\n- Observed: ${compendia.toSet}")
      ZIO.succeed(Seq());
    } else {
      ZStream.fromIterable(compendia)
        .map(compendium => {

          compendium.filename
        }).runCollect
    }
  }

  def validateSynonyms(pw: PrintWriter, output: BabelOutput): ZIO[Blocking with Console, Throwable, Seq[String]] = {
    val synonyms = output.synonyms
    if (synonyms.keySet != EXPECTED_SYNONYMS) {
      pw.println(s"ERROR: synonyms missing\n- Expected: ${EXPECTED_SYNONYMS}\n- Observed: ${synonyms.toSet}")
      ZIO.succeed(Seq());
    } else {
      ZStream.fromIterable(synonyms)
        .map({ case (filename, synonym) => {

          filename
        }}).runCollect
    }
  }

  def validateConflations(pw: PrintWriter, output: BabelOutput): ZIO[Blocking with Console, Throwable, Seq[String]] = {
    val conflations = output.conflations
    if (conflations.toSet != EXPECTED_CONFLATIONS) {
      pw.println(s"ERROR: conflations missing\n- Expected: ${EXPECTED_CONFLATIONS}\n- Observed: ${conflations.toSet}")
      ZIO.succeed(Seq());
    } else {
      ZStream.fromIterable(conflations)
        .map(conflation => {

          conflation
        }).runCollect
    }
  }
}
