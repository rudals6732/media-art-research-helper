# run_tests.ps1 -- 통합 테스트 러너 (PowerShell 5.1)
# 사용: .\run_tests.ps1

$ErrorActionPreference = "Continue"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:PASS = 0
$script:FAIL = 0
$script:SKIP = 0

function Write-Result {
    param([string]$label, [string]$status, [string]$detail = "")
    $color = "Yellow"
    if ($status -eq "PASS") { $color = "Green" }
    if ($status -eq "FAIL") { $color = "Red"   }
    Write-Host "  [$status] $label" -ForegroundColor $color
    if ($detail) { Write-Host "        $detail" -ForegroundColor DarkGray }
    if ($status -eq "PASS") { $script:PASS++ }
    elseif ($status -eq "FAIL") { $script:FAIL++ }
    else { $script:SKIP++ }
}

Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  JARVIS / Media-Art Integration Test" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# -----------------------------------------------------------------------
# 1. 환경 확인
# -----------------------------------------------------------------------
Write-Host "[1] Environment" -ForegroundColor White

$javaCmd  = Get-Command java  -ErrorAction SilentlyContinue
$javacCmd = Get-Command javac -ErrorAction SilentlyContinue
$mvnCmd   = Get-Command mvn   -ErrorAction SilentlyContinue

if ($javaCmd) {
    $jver = (java -version 2>&1)[0].ToString()
    Write-Result "Java runtime"  "PASS" $jver
} else {
    Write-Result "Java runtime"  "FAIL" "java not found"
}

if ($javacCmd) {
    $jcver = (javac -version 2>&1).ToString()
    Write-Result "Java compiler" "PASS" $jcver
} else {
    Write-Result "Java compiler" "FAIL" "javac not found"
}

if ($mvnCmd) {
    $mver = (mvn --version 2>&1)[0].ToString()
    Write-Result "Maven" "PASS" $mver
} else {
    Write-Result "Maven" "SKIP" "Not installed -- https://maven.apache.org/download.cgi"
}

$py = $null
$pyCandidates = @(
    "python", "python3", "py",
    "C:\Python313\python.exe", "C:\Python312\python.exe", "C:\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
)
foreach ($c in $pyCandidates) {
    if ($py) { break }
    $found = Get-Command $c -ErrorAction SilentlyContinue
    if ($found) { $py = $found.Source }
}

if ($py) {
    $pyver = (& $py --version 2>&1).ToString()
    Write-Result "Python" "PASS" $pyver
} else {
    Write-Result "Python" "SKIP" "Not installed -- https://www.python.org/downloads/"
}

# -----------------------------------------------------------------------
# 2. 프로젝트 파일 구조
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "[2] Project File Structure" -ForegroundColor White

$requiredFiles = @(
    "CLAUDE.md",
    "scrapper-python\src\crawler.py",
    "scrapper-python\src\validator.py",
    "scrapper-python\src\text_processor.py",
    "scrapper-python\src\__init__.py",
    "scrapper-python\run.py",
    "scrapper-python\requirements.txt",
    "scrapper-python\.env.example",
    "backend-java\pom.xml",
    "backend-java\src\main\java\com\project\MediaArtApplication.java",
    "backend-java\src\main\java\com\project\controller\PaperController.java",
    "backend-java\src\main\java\com\project\service\ReportService.java",
    "backend-java\src\main\java\com\project\model\Paper.java",
    "backend-java\src\main\java\com\project\model\ReportSection.java",
    "jarvis-core\config.json",
    "jarvis-core\src\jarvis_agent.py",
    "jarvis-core\src\os_bridge.py",
    "jarvis-core\src\voice_handler.py",
    "output\research_notes\.gitkeep",
    "output\reports\.gitkeep"
)

foreach ($f in $requiredFiles) {
    $fullPath = Join-Path $ROOT $f
    if (Test-Path $fullPath) {
        Write-Result $f "PASS"
    } else {
        Write-Result $f "FAIL" "Missing: $fullPath"
    }
}

# -----------------------------------------------------------------------
# 3. Java 모델 컴파일
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "[3] Java Model Compilation (javac)" -ForegroundColor White

if ($javacCmd) {
    $srcDir = "$ROOT\backend-java\src\main\java\com\project"
    $outDir = "$ROOT\backend-java\build\classes"
    New-Item -ItemType Directory -Force $outDir | Out-Null

    $compileOut = javac -encoding UTF-8 -d $outDir `
        "$srcDir\model\Paper.java" `
        "$srcDir\model\ReportSection.java" 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Result "Paper.java"         "PASS" "Compiled OK"
        Write-Result "ReportSection.java" "PASS" "Compiled OK"
    } else {
        $errMsg = ($compileOut | Out-String).Trim()
        Write-Result "Java model compile" "FAIL" $errMsg
    }
} else {
    Write-Result "Java model compile" "SKIP" "javac not available"
}

# -----------------------------------------------------------------------
# 4. Python 패키지 확인
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "[4] Python Package Check" -ForegroundColor White

if ($py) {
    $packages = @("requests", "bs4", "lxml", "flask", "dotenv")
    foreach ($pkg in $packages) {
        $checkResult = & $py -c "import $pkg" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Result $pkg "PASS"
        } else {
            Write-Result $pkg "FAIL" "Run: pip install -r scrapper-python/requirements.txt"
        }
    }
} else {
    Write-Result "Python packages" "SKIP" "Python not installed"
}

# -----------------------------------------------------------------------
# 5. Python 유닛 테스트
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "[5] Python Unit Tests" -ForegroundColor White

if ($py) {
    $testFiles = @(
        "$ROOT\scrapper-python\tests\test_text_processor.py",
        "$ROOT\scrapper-python\tests\test_validator.py",
        "$ROOT\jarvis-core\tests\test_intent_parser.py"
    )
    foreach ($tf in $testFiles) {
        $name = Split-Path $tf -Leaf
        $testOut = & $py -m unittest $tf -v 2>&1
        if ($LASTEXITCODE -eq 0) {
            $okCount = ($testOut | Select-String "OK").Count
            Write-Result $name "PASS" "All assertions passed"
        } else {
            $errLines = $testOut | Select-String "FAIL:|ERROR:" | Select-Object -First 2
            $errMsg = ($errLines | Out-String).Trim() -replace "`r`n", " | "
            Write-Result $name "FAIL" $errMsg
        }
    }
} else {
    Write-Result "test_text_processor.py" "SKIP" "Python not installed"
    Write-Result "test_validator.py"      "SKIP" "Python not installed"
    Write-Result "test_intent_parser.py"  "SKIP" "Python not installed"
}

# -----------------------------------------------------------------------
# 6. Flask 서버 스모크 테스트
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "[6] Flask Server Smoke Test" -ForegroundColor White

if ($py) {
    $flaskProc = Start-Process -FilePath $py `
        -ArgumentList "$ROOT\scrapper-python\run.py" `
        -WorkingDirectory "$ROOT\scrapper-python" `
        -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 3

    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:5000/health" -TimeoutSec 5 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            Write-Result "GET /health" "PASS" "HTTP 200 ok"
        } else {
            Write-Result "GET /health" "FAIL" "HTTP $($resp.StatusCode)"
        }
    } catch {
        $errDetail = $_.Exception.Message
        Write-Result "GET /health" "FAIL" $errDetail
    }

    Stop-Process -Id $flaskProc.Id -Force -ErrorAction SilentlyContinue
} else {
    Write-Result "Flask smoke test" "SKIP" "Python not installed"
}

# -----------------------------------------------------------------------
# 7. Maven 빌드
# -----------------------------------------------------------------------
Write-Host ""
Write-Host "[7] Maven Build & Test" -ForegroundColor White

if ($mvnCmd) {
    $mvnOut = mvn -f "$ROOT\backend-java\pom.xml" test -q 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Result "mvn test" "PASS" "All JUnit tests passed"
    } else {
        $errLines = ($mvnOut | Select-Object -Last 5 | Out-String).Trim()
        Write-Result "mvn test" "FAIL" $errLines
    }
} else {
    Write-Result "mvn test" "SKIP" "Maven not installed -- https://maven.apache.org/download.cgi"
}

# -----------------------------------------------------------------------
# 결과 요약
# -----------------------------------------------------------------------
$total = $script:PASS + $script:FAIL + $script:SKIP
Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
$summaryColor = if ($script:FAIL -gt 0) { "Red" } else { "Green" }
Write-Host ("  PASS {0} / FAIL {1} / SKIP {2}  (Total {3})" -f $script:PASS, $script:FAIL, $script:SKIP, $total) -ForegroundColor $summaryColor
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

if ($script:FAIL -gt 0) { exit 1 } else { exit 0 }
