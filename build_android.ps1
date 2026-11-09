param(
    [ValidateSet("debug", "profile", "release")]
    [string]$Mode = "debug",
    [string]$OutputDir = "",
    [string]$ReleasePassword = $env:LIP_READER_RELEASE_PASSWORD
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# For repeatable local release builds, a password may be stored as a
# user-bound DPAPI credential outside source control. Environment/parameter
# values still take precedence for CI and managed signing services.
if ($Mode -eq "release" -and [string]::IsNullOrWhiteSpace($ReleasePassword)) {
    $credentialPath = Join-Path $projectRoot "android\signing\release-signing.clixml"
    if (Test-Path -LiteralPath $credentialPath) {
        $credential = Import-Clixml -LiteralPath $credentialPath
        $ReleasePassword = $credential.GetNetworkCredential().Password
    }
}

$gradleCache = [Environment]::GetEnvironmentVariable(
    "GRADLE_USER_HOME",
    "User"
)
$pubCache = [Environment]::GetEnvironmentVariable("PUB_CACHE", "User")
$env:GRADLE_USER_HOME = if ($gradleCache -and (Test-Path -LiteralPath (Split-Path -Qualifier $gradleCache))) {
    $gradleCache
} else {
    Join-Path $env:USERPROFILE '.gradle'
}
$env:PUB_CACHE = if ($pubCache -and (Test-Path -LiteralPath (Split-Path -Qualifier $pubCache))) {
    $pubCache
} else {
    Join-Path $env:LOCALAPPDATA 'Pub\Cache'
}

Set-Location -LiteralPath $projectRoot
Write-Output "GRADLE_USER_HOME=$env:GRADLE_USER_HOME"
Write-Output "PUB_CACHE=$env:PUB_CACHE"

if ($Mode -eq "release") {
    $signingDir = Join-Path $projectRoot "android\signing"
    $keystorePath = Join-Path $signingDir "lip-reader-test-release.jks"
    $keyAlias = "lip-reader-test-release"
    if ([string]::IsNullOrWhiteSpace($ReleasePassword)) {
        throw (
            "Set LIP_READER_RELEASE_PASSWORD or pass -ReleasePassword " +
            "when building a signed release APK. The password is never " +
            "stored in source control."
        )
    }
    if (-not (Test-Path -LiteralPath $keystorePath)) {
        New-Item -ItemType Directory -Path $signingDir -Force | Out-Null
        $keytoolCommand = Get-Command keytool -ErrorAction SilentlyContinue
        $keytoolPath = if ($keytoolCommand) {
            $keytoolCommand.Source
        } elseif (Test-Path -LiteralPath "C:\Program Files\Java\jdk-21\bin\keytool.exe") {
            "C:\Program Files\Java\jdk-21\bin\keytool.exe"
        } else {
            throw "keytool.exe was not found. Install a JDK or add keytool to PATH."
        }
        & $keytoolPath `
            -genkeypair `
            -v `
            -keystore $keystorePath `
            -storepass $ReleasePassword `
            -keypass $ReleasePassword `
            -alias $keyAlias `
            -keyalg RSA `
            -keysize 3072 `
            -validity 3650 `
            -dname "CN=Lip Reader Internal Distribution, OU=Mobile, O=Lip Reader, L=Ho Chi Minh City, C=VN"
        if ($LASTEXITCODE -ne 0) {
            throw "Could not create the local release keystore."
        }
    }
    $env:LIP_READER_KEYSTORE_PATH = $keystorePath
    $env:LIP_READER_KEYSTORE_PASSWORD = $ReleasePassword
    $env:LIP_READER_KEY_ALIAS = $keyAlias
    $env:LIP_READER_KEY_PASSWORD = $ReleasePassword
}

flutter analyze
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
flutter test
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
& flutter build apk "--$Mode"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$sourceApk = Join-Path $projectRoot "build\app\outputs\flutter-apk\app-$Mode.apk"
if (-not (Test-Path -LiteralPath $sourceApk)) {
    throw "APK output was not found: $sourceApk"
}
if ($OutputDir) {
    $resolvedOutputDir = [IO.Path]::GetFullPath($OutputDir)
    New-Item -ItemType Directory -Path $resolvedOutputDir -Force | Out-Null
    $versionLine = Get-Content -LiteralPath (Join-Path $projectRoot 'pubspec.yaml') |
        Where-Object { $_ -match '^version:\s*([0-9.]+)' } | Select-Object -First 1
    if ($versionLine -notmatch '^version:\s*([0-9.]+)') { throw 'App version not found.' }
    $appVersion = $Matches[1]
    $targetApk = Join-Path $resolvedOutputDir "VietLip-$appVersion-$Mode.apk"
    Copy-Item -LiteralPath $sourceApk -Destination $targetApk -Force
    Write-Output "APK packaged: $targetApk"
} else {
    Write-Output "APK built: $sourceApk"
}
exit 0
