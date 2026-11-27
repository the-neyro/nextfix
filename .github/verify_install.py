"""Exercise both one-line bootstrap entry points with a temporary Git remote."""

import asyncio
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


SOURCE = Path(__file__).resolve().parent.parent
OLD_TAG = "v0.2.3"
OLD_COMMIT = "aeb3800b75d732ef68efbeb8b6ca03a29f7ac1fc"
NEW_TAG = "v999999.0.0"
PROJECT = {"domain": "127.0.0.1", "name": "Projekt aus der alten Installation"}


def git(*args, cwd=SOURCE):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def seed_db():
    from fastapi.testclient import TestClient

    from app.web import app

    with TestClient(app) as client:
        response = client.post("/api/projekte", json=PROJECT)
        assert response.status_code == 201, response.text
        assert response.json()["id"] == 1


def smoke_test():
    from fastapi.testclient import TestClient

    from app.mcp_server import server as mcp
    from app.web import app
    from scripts.demo_website import starten

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        projects = client.get("/api/projekte").json()
        assert len(projects) == 1 and projects[0].items() >= PROJECT.items(), projects
        assert projects[0]["id"] == 1
        demo, url = starten()
        try:
            settings = client.put(
                "/api/projekte/1/einstellungen",
                json={"start_url": url, "crawl_delay": 0, "seitenlimit": 3},
            )
            assert settings.status_code == 200, settings.text
            crawl = client.post("/api/projekte/1/crawls?warten=true").json()
            assert crawl["status"] == "fertig" and crawl["seiten_anzahl"] > 0, crawl
            tasks = client.get(f"/api/crawls/{crawl['id']}/aufgaben").json()["aufgaben"]
            assert tasks
            result = asyncio.run(mcp.call_tool("was_jetzt_tun", {"projekt_id": 1}))
            assert tasks[0]["was"] in str(result)
        finally:
            demo.shutdown()
            demo.server_close()


def verify():
    windows = sys.platform == "win32"
    if windows:
        command = [
            "pwsh", "-NoProfile", "-NonInteractive", "-Command",
            "[Console]::InputEncoding = [Text.UTF8Encoding]::new($false); "
            "Invoke-Expression ([Console]::In.ReadToEnd())",
        ]
        script = SOURCE / "scripts/install.ps1"
    else:
        command = ["bash"]
        script = SOURCE / "scripts/install.sh"
    bootstrap_source = script.read_text(encoding="utf-8")

    with TemporaryDirectory(prefix="nextfix-install-") as temp:
        temp = Path(temp)
        remote = temp / "releases.git"
        install = temp / "Nextfix installiert"
        python = install / (".venv/Scripts/python.exe" if windows else ".venv/bin/python")

        env = {
            **os.environ,
            "NEXTFIX_START": "nein",
            "NEXTFIX_DIR": str(install),
            "NEXTFIX_REPO": remote.as_uri(),
            "SEO_DB": str(install / "data/seo.db"),
            "SEO_GSC_SCHLUESSEL": str(temp / "unused-gsc"),
            "SEO_BING_SCHLUESSEL": str(temp / "unused-bing"),
            "SEO_OPR_SCHLUESSEL": str(temp / "unused-opr"),
            "PYTHONPATH": str(install),
        }
        env.pop("NEXTFIX_BRANCH", None)

        def bootstrap(expect_success=True):
            result = subprocess.run(
                command, input=bootstrap_source, encoding="utf-8", cwd=temp, env=env, check=False,
            )
            if expect_success:
                result.check_returncode()
            else:
                assert result.returncode != 0 and not install.exists()

        # Unreachable remote, then reachable remote with only a development branch.
        bootstrap(expect_success=False)
        git("init", "--bare", str(remote))
        git("push", remote.as_uri(), "HEAD:refs/heads/main")
        bootstrap(expect_success=False)

        # Install the previous release and create data using its real schema.
        assert git("rev-parse", OLD_TAG) == OLD_COMMIT
        git("push", remote.as_uri(), f"{OLD_COMMIT}:refs/tags/{OLD_TAG}")
        bootstrap()
        assert git("rev-parse", "HEAD", cwd=install) == OLD_COMMIT
        subprocess.run([python, __file__, "seed"], cwd=install, env=env, check=True)

        # A newer prerelease and a branch sharing the stable tag name must not win.
        candidate = git("rev-parse", "HEAD")
        git("update-ref", f"refs/heads/{NEW_TAG}", OLD_COMMIT, cwd=remote)
        git("update-ref", f"refs/tags/{NEW_TAG}-rc.1", candidate, cwd=remote)
        git("-c", "user.name=Install CI", "-c", "user.email=install-ci@example.invalid",
            "tag", "-a", NEW_TAG, "-m", "Install smoke test", candidate, cwd=remote)
        bootstrap()
        assert git("rev-parse", "HEAD", cwd=install) == candidate
        subprocess.run([python, __file__, "smoke"], cwd=install, env=env, check=True)

        # The explicitly requested branch works when there are no stable tags.
        git("update-ref", "-d", f"refs/tags/{OLD_TAG}", cwd=remote)
        git("update-ref", "-d", f"refs/tags/{NEW_TAG}", cwd=remote)
        env["NEXTFIX_BRANCH"] = "main"
        bootstrap()
        assert git("rev-parse", "HEAD", cwd=install) == candidate


if __name__ == "__main__":
    if sys.argv[1:] == ["seed"]:
        seed_db()
    elif sys.argv[1:] == ["smoke"]:
        smoke_test()
    else:
        verify()
