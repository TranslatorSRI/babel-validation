package org.renci.babel.utils

object MemoryUtils {
  def getMemorySummary: String = {
    val runtime = Runtime.getRuntime

    def bytesToGB(b: Long): Double = b.toDouble / (1e+9)

    f"${bytesToGB(runtime.freeMemory())}%.2f GB free out of ${bytesToGB(runtime.totalMemory())}%.2f GB (${bytesToGB(runtime.maxMemory())}%.2f max GB)"
  }
}
