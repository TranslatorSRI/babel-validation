import sbt._

object Dependencies {
  // Shared versions
  val zioVersion = "1.0.14"

  // Dependencies
  lazy val scallop = "org.rogach" %% "scallop" % "4.1.0"
  lazy val zio = "dev.zio" %% "zio" % zioVersion
  lazy val zioStreams = "dev.zio" %% "zio-streams" % zioVersion

  lazy val scalaLogging = "com.typesafe.scala-logging" %% "scala-logging" % "3.9.4"
  lazy val logback = "ch.qos.logback" % "logback-classic" % "1.2.11"

  // Testing
  lazy val scalaTest = "org.scalatest" %% "scalatest" % "3.2.12"
}
