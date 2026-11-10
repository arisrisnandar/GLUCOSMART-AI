// Mendefinisikan plugin di level root
plugins {
    id("com.google.gms.google-services") version "4.4.2" apply false
}

allprojects {
    repositories {
        google()
        mavenCentral()
    }
    
    // Konfigurasi Dependency Locking untuk keamanan dan prediktabilitas versi
    configurations.all {
        resolutionStrategy.dependencyLocking {
            // Kunci semua konfigurasi yang dapat di-resolve (termasuk transitive dependencies)
            lockAllConfigurations()
            
            // (OPSIONAL) Jika Anda ingin mengabaikan beberapa konfigurasi spesifik dari penguncian
            // ignoredConfigurations.addAll(listOf("lintChecks", "lintPublish"))
        }
    }
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
}

// Task untuk membersihkan direktori build
tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
