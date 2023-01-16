package org.renci.babel.utils.model

import java.io.File

/**
 * A BabelOutput is a directory containing Babel output results.
 */
class BabelOutput(root: File) {

  /** A description of this BabelOutput. */
  override def toString: String = {
    s"BabelOutput(${root}) containing ${compendia.length} compendia"
  }

  /**
   * Return a list of all the files in a subdirectory of this BabelOutput.
   * @param dirName
   *   The subdirectory name.
   * @return
   *   The list of files in the {BabelOutput root}/{subdirectory}.
   */
  def getFilesInDir(dirName: String): Seq[String] = {
    val dir = new File(root, dirName)
    if (!dir.exists()) return Seq()
    val filenames = dir.list()
    // TODO: this would be a good place to look for out-of-place files.
    filenames.toSeq
  }

  /**
   * The compendia directory in this BabelOutput.
   */
  val compendiaDir: File = new File(root, "compendia")

  /**
   * A list of all the compendia in this BabelOutput.
   */
  lazy val compendia: Seq[Compendium] =
    getFilesInDir("compendia").map(filename =>
      new Compendium(new File(compendiaDir, filename))
    )

  /**
   * The synonyms directory in this BabelOutput.
   */
  val synonymDir: File = new File(root, "synonyms")

  /**
   * A dictionary of synonym files in the synonyms/ directory.
   */
  lazy val synonyms: Map[String, Synonyms] =
    getFilesInDir("synonyms")
      .map(filename => (filename, new Synonyms(new File(synonymDir, filename))))
      .toMap

  /**
   * The conflations directory in this BabelOutput.
   */
  val conflationsDir: File = new File(root, "conflation")

  /**
   * A list of conflations in the conflations/ directory.
   */
  lazy val conflations: Seq[Conflations] =
    getFilesInDir("conflations").map(filename =>
      new Conflations(new File(conflationsDir, filename))
    )
}
