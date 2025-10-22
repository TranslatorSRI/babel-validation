package org.renci.babel.utils.model

import zio.ZIO
import zio.blocking.Blocking
import zio.stream.{ZStream, ZTransducer}

import java.io.File
import java.nio.file.Path

/**
 * A single synonym from a synonyms file in the Babel output.
 */
case class Synonym(
    id: String,
    relation: String,
    synonym: String
)

/**
 * A synonyms file in the Babel output.
 */
class Synonyms(file: File) {
  val filename: String = file.getName
  val path: Path = file.toPath

  /**
   * A ZStream of all the lines in this file as strings.
   */
  lazy val lines: ZStream[Blocking, Throwable, String] = {
    ZStream
      .fromFile(path)
      .aggregate(ZTransducer.utf8Decode)
      .aggregate(ZTransducer.splitLines)
  }

  /**
   * A ZStream of all the synonyms in this file.
   */
  lazy val synonyms: ZStream[Blocking, Throwable, Synonym] = {
    lines.flatMap(line => {
      val pattern = "^(.*?)\t(.*?)\t(.*)$".r
      line match {
        case pattern(id, relation, synonym) =>
          ZStream.succeed(Synonym(id, relation, synonym))
        case _ =>
          ZStream.fail(
            new RuntimeException(
              s"Could not parse line in synonym file ${file}: ${line}"
            )
          )
      }
    })
  }

  /**
   * Load all of the synonyms into a Map so that they can be looked up by ID.
   */
  // TODO: we ignore the relation for now, but we should probably check that here.
  lazy val synonymsById: ZIO[Blocking, Throwable, Map[String, Seq[Synonym]]] =
    synonyms.runCollect
      .map(chunk => chunk.map(s => (s.id, s)).groupMap(_._1)(_._2))
}
