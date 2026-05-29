"""로컬 파일 시스템 및 터미널 자동 실행 브릿지.

보안 원칙
  - 허용 명령어 화이트리스트만 실행 (config.json os_bridge.allowed_commands)
  - subprocess는 항상 shell=False + 인자 리스트로 호출
  - 파일 접근은 allowed_base_paths 하위로만 제한
  - 실행 전 _guard() 검사를 반드시 통과해야 함
"""

import json
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent / "config.json"


def _load_cfg() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f).get("os_bridge", {})


class OsBridge:
    def __init__(self):
        cfg = _load_cfg()
        self._allowed_cmds: list[str] = cfg.get("allowed_commands", [])
        self._allowed_bases: list[Path] = [
            Path(p).resolve() for p in cfg.get("allowed_base_paths", [])
        ]

    # ------------------------------------------------------------------
    # 보안 가드
    # ------------------------------------------------------------------

    def _guard_cmd(self, cmd: str) -> None:
        """허용 명령어 화이트리스트 검사."""
        if cmd not in self._allowed_cmds:
            raise PermissionError(
                f"허용되지 않은 명령어: '{cmd}'. "
                f"허용 목록: {self._allowed_cmds}"
            )

    def _guard_path(self, path: str | Path) -> Path:
        """경로가 allowed_base_paths 하위인지 검사 후 절대 경로 반환."""
        resolved = Path(path).resolve()
        for base in self._allowed_bases:
            try:
                resolved.relative_to(base)
                return resolved
            except ValueError:
                continue
        raise PermissionError(
            f"허용 경로 범위 초과: '{resolved}'. "
            f"허용 기준 경로: {self._allowed_bases}"
        )

    # ------------------------------------------------------------------
    # 터미널 실행
    # ------------------------------------------------------------------

    def run(
        self,
        cmd: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        timeout: int = 60,
    ) -> dict:
        """화이트리스트 명령어를 shell=False로 실행.

        Returns:
            {"returncode": int, "stdout": str, "stderr": str}
        """
        self._guard_cmd(cmd)
        full_cmd = [cmd] + (args or [])
        logger.info("실행: %s", " ".join(full_cmd))

        result = subprocess.run(
            full_cmd,
            shell=False,           # 인젝션 방지
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    # ------------------------------------------------------------------
    # 파일 시스템
    # ------------------------------------------------------------------

    def read_file(self, path: str) -> str:
        """허용 경로 내 파일 읽기."""
        safe = self._guard_path(path)
        return safe.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> None:
        """허용 경로 내 파일 쓰기 (상위 디렉토리 자동 생성)."""
        safe = self._guard_path(path)
        safe.parent.mkdir(parents=True, exist_ok=True)
        safe.write_text(content, encoding="utf-8")
        logger.info("파일 저장: %s", safe)

    def list_dir(self, path: str) -> list[str]:
        """허용 경로 내 디렉토리 목록 반환."""
        safe = self._guard_path(path)
        return [str(p) for p in safe.iterdir()]

    def delete_file(self, path: str) -> None:
        """허용 경로 내 파일 삭제 (디렉토리 불가)."""
        safe = self._guard_path(path)
        if safe.is_dir():
            raise IsADirectoryError(f"디렉토리 삭제는 지원하지 않습니다: {safe}")
        safe.unlink()
        logger.info("파일 삭제: %s", safe)
