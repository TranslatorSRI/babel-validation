package org.renci.babel.utils.model

import zio.ZIO
import zio.blocking.Blocking
import zio.stream.{ZStream, ZTransducer}
import zio.json._

import java.io.File
import java.nio.file.Path

/**
 * A single conflation from a conflations file in the Babel output.
 */
case class Conflation(
    conflatedIds: Seq[String]
)

/**
 * A synonyms file in the Compendium output.
 */
class Conflations(file: File) {
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
  lazy val conflations: ZStream[Blocking, Throwable, Conflation] = {
    val arrayDecoder = JsonDecoder[Seq[String]]

    lines.zipWithIndex.flatMap({
      case (line, index) => arrayDecoder.decodeJson(line).fold(
        error => ZStream.fail(new RuntimeException(s"Could not parse line ${index + 1} of file ${filename}: ${error} (line: ${line})")),
        conflatedIds => ZStream.succeed(Conflation(conflatedIds))
      )
    })
  }

  /**
   * Load all of the synonyms into a Map so that they can be looked up by ID.
   */
  // TODO: we ignore the relation for now, but we should probably check that here.
  lazy val conflationsById: ZIO[Blocking, Throwable, Map[String, Seq[Conflation]]] =
    conflations.runCollect
      .map(chunk => chunk.flatMap(s => {
        s.conflatedIds.map { id => (id, s)}
      }).groupMap(_._1)(_._2))
}
