// Mendefinisikan plugin di level root menggunakan Version Catalog
plugins {
    alias(libs.plugins.google.services) apply false
}

// Mengatur direktori build kustom untuk proyek root
val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

// Mengatur direktori build untuk setiap sub-proyek (termasuk :app)
subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}

subprojects {
    project.evaluationDependsOn(":app")
    
    // Konfigurasi Dependency Locking untuk keamanan dan prediktabilitas versi
    configurations.all {
        resolutionStrategy.dependencyLocking {
            // Kunci semua konfigurasi
            lockAllConfigurations()
        }
    }
}

// Task untuk membersihkan direktori build
tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
