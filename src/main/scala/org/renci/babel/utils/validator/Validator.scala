package org.renci.babel.utils.validator

import com.typesafe.scalalogging.LazyLogging
import org.renci.babel.utils.cli.Utils.SupportsFilenameFiltering
import org.renci.babel.utils.model.{BabelOutput, Compendium}
import org.rogach.scallop.{ScallopOption, Subcommand}
import zio.ZIO
import zio.json._
import zio.blocking.Blocking
import zio.console.Console
import zio.stream.ZStream

import java.io.{File, FileWriter, PrintWriter}
import scala.collection.{Set, immutable}

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
          compendia <- validateCompendia(pw, babelOutput)
          synonyms <- validateSynonyms(pw, babelOutput)
          conflations <- validateConflations(pw, babelOutput)
        } yield {
          val failedCompendia = compendia.filter(!_.valid)

          pw.println(s"== COMPENDIA [${compendia.size}] ==")
          compendia.foreach({ compendium =>
            pw.println(
              s" - ${compendium.compendium.filename} [${if (compendium.valid) "valid"
                else "INVALID"}]: types=${compendium.types}, prefixes=${compendium.prefixes}, ${compendium.recordCount} records"
            )
          })
          if (failedCompendia.nonEmpty) {
            val err =
              s"${failedCompendia.size} compendia failed validation: [${failedCompendia
                  .map(_.compendium.filename)
                  .mkString(", ")}]"
            logger.error(err)
          }
          pw.println(s"Total record count: ${compendia.map(_.recordCount).sum}")
          pw.println()

          logger.info(
            s"Validated synonyms [${synonyms.size}]: ${synonyms}"
          )
          pw.println(s"== SYNONYMS [${synonyms.size}] ==")
          synonyms.foreach({ synonym =>
            pw.println(
              s" - ${synonym.filename}: ${synonym.uniqueIds.size} unique IDs, ${synonym.uniqueRelations.size} unique relations (${synonym.uniqueRelations
                  .mkString(", ")}), ${synonym.uniqueSynonyms.size} unique synonyms."
            )
          })
          pw.println()

          logger.info(
            s"Validated conflations [${conflations.size}]: ${conflations}"
          )
          pw.println(s"== CONFLATIONS [${conflations.size}] ==")
          conflations.foreach({ conflation =>
            pw.println(
              s" - ${conflation.filename}: ${conflation.uniqueIds} unique identifiers across ${conflation.confCount} conflations."
            )
          })

          /*
           * Calculate prefix counts (specifically for https://github.com/TranslatorSRI/NodeNormalization/issues/153#issuecomment-1323664976)
           */
          case class PrefixCount(
              filename: String,
              typ: String,
              prefix: String,
              count: Long
          )
          val prefixCounts = compendia.flatMap(compendium => for {
            typ <- compendium.prefixesByType.keySet
            (prefix, count) <- compendium.prefixesByType.getOrElse(typ, Map[String, Long]())
          } yield PrefixCount(compendium.compendium.filename, typ, prefix, count))

          // To simulate the /get_curie_prefixes endpoint, we want this to be in the format:
          // {typ}\t{prefix}\t{count}
          val curiePrefixCounts = prefixCounts.groupBy(_.typ)
            .map(t => (t._1, t._2.groupMapReduce(_.prefix)(_.count)(_ + _)))

          pw.println("\n== get_curie_prefixes ==")
          pw.println(curiePrefixCounts)
          pw.println(curiePrefixCounts.toJsonPretty)
        }
      }
  }

  case class CompendiumSummary(
      compendium: Compendium,
      valid: Boolean,
      recordCount: Long,
      types: Set[String],
      prefixes: Map[String, Long],
      prefixesByType: Map[String, Map[String, Long]]
  )

  def validateCompendia(
      pw: PrintWriter,
      output: BabelOutput
  ): ZIO[Blocking with Console, Throwable, Seq[CompendiumSummary]] = {
    val compendia = output.compendia
    val compendiaFilenames = compendia.map(_.filename).toSet
    if (compendiaFilenames != EXPECTED_COMPENDIA) {
      val errorStr =
        s"""FAIL: compendia missing or extra
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
              val prefixRegex = "^(.*):(.*?)$".r

              identifierOpt match {
                case Some(identifier) =>
                  identifier match {
                    case prefixRegex(prefix, _) => prefix
                    case _ => {
                      logger.warn(
                        s"Could not determine prefix for identifier ${identifier}"
                      )
                      identifier
                    }
                  }
                case None => "(no identifier)"
              }
            }).groupBy(identity).map(t => (t._1, t._2.size))
        } yield (typ, prefixes)

        val results = zio.Runtime.default.unsafeRun(resultsZS.runCollect)
        val recordCount = results.size
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
              s"SUCCESS: compendium $compendium passed validation with ${recordCount} records."
            logger.info(successStr)
            pw.println(successStr)
            pw.flush()
            true
          }
        }

        val resultMap = results.toMap

        CompendiumSummary(
          compendium,
          valid,
          recordCount,
          resultMap.keySet,
          resultMap.values.flatten.groupMapReduce(_._1)(_._2)(_ + _),
          resultMap
        )
      })
      .runCollect
  }

  case class SynonymSummary(
      filename: String,
      uniqueIds: Set[String],
      uniqueRelations: Set[String],
      uniqueSynonyms: Set[String]
  )

  def validateSynonyms(
      pw: PrintWriter,
      output: BabelOutput
  ): ZIO[Blocking with Console, Throwable, Seq[SynonymSummary]] = {
    val synonyms = output.synonyms
    if (synonyms.keySet != EXPECTED_SYNONYMS) {
      pw.println(
        s"""FAIL: synonyms missing or extra
           | - Expected: ${EXPECTED_SYNONYMS}
           | - Observed: ${synonyms.keySet}
           |   - Extra files: ${synonyms.keySet.diff(EXPECTED_SYNONYMS)}
           |   - Missing files: ${EXPECTED_SYNONYMS.diff(
            synonyms.keySet
          )}""".stripMargin
      )
      ZIO.succeed(Seq());
    } else {
      for {
        summaries <- ZStream
          .fromIterable(synonyms)
          .mapM({ case (filename, synonyms) =>
            for {
              uniqueCounts <- synonyms.synonyms.fold(
                (
                  immutable.Set[String](),
                  immutable.Set[String](),
                  immutable.Set[String]()
                )
              ) { case ((ids, relations, syns), synonyms) =>
                (
                  ids + synonyms.id,
                  relations + synonyms.relation,
                  syns + synonyms.synonym
                )
              }
            } yield SynonymSummary(
              filename,
              uniqueCounts._1,
              uniqueCounts._2,
              uniqueCounts._3
            )
          })
      } yield summaries
    }.runCollect
  }

  case class ConflationSummary(
      filename: String,
      uniqueIds: Set[String],
      confCount: Long
  )

  def validateConflations(
      pw: PrintWriter,
      output: BabelOutput
  ): ZIO[Blocking with Console, Throwable, Seq[ConflationSummary]] = {
    val conflations = output.conflations
    val conflationFilenames = conflations.map(_.filename).toSet
    if (conflationFilenames != EXPECTED_CONFLATIONS) {
      pw.println(
        s"""FAIL: conflations missing or extra
           | - Expected: ${EXPECTED_CONFLATIONS}
           | - Observed: ${conflationFilenames}
           |   - Extra files: ${conflationFilenames.diff(EXPECTED_CONFLATIONS)}
           |   - Missing files: ${EXPECTED_CONFLATIONS.diff(
            conflationFilenames
          )}""".stripMargin
      )
      ZIO.succeed(Seq());
    } else {
      ZStream
        .fromIterable(conflations)
        .mapM(conflation =>
          for {
            confCount <- conflation.conflations.runCount
            confsById <- conflation.conflationsById
          } yield ConflationSummary(
            conflation.filename,
            confsById.keySet,
            confCount
          )
        )
        .runCollect
    }
  }
}
