package org.renci.babel.utils

object MemoryUtils {
  def getMemorySummary: String = {
    val runtime = Runtime.getRuntime

    def bytesToGB(b: Long): Double = b.toDouble / (1e+9)

    val memoryUsed = runtime.totalMemory() - runtime.freeMemory()

    f"${bytesToGB(runtime.freeMemory())}%.2f GB free out of ${bytesToGB(
        runtime.totalMemory()
      )}%.2f GB (${bytesToGB(memoryUsed)}%.2f GB used out of ${bytesToGB(runtime.maxMemory())}%.2f GB max)"
  }
}
