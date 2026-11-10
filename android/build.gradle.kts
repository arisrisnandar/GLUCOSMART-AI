plugins {
    id("com.google.gms.google-services") apply false  // ← TAMBAH
}

allprojects {
    repositories {
        google()
        mavenCentral()
    }
    
    // Mengaktifkan dependency locking untuk memastikan versi dependensi konsisten dan dapat diprediksi
    configurations.all {
        resolutionStrategy.dependencyLocking {
            lockAllConfigurations()
        }
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
subprojects {
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
