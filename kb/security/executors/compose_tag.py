"""Image swap: the compose service's image tag moves to the fixed release. The compose file lives on the server and the
agent never enters a server, so this executor writes the diff and the exact server commands into the order; the person
runs them and pastes the result; `close --reason patched` follows after the inventory shows the new version."""
from __future__ import annotations


def plan(service: str, image: str, from_tag: str, to_tag: str, critical: bool, compose_path_on_server: str = "<compose 파일 경로>") -> dict:
    return {"executor": "compose_tag", "condition": "none" if critical else "minutes-swap", "downtime_expected": "minutes",
            "service": service, "image": image, "from_version": from_tag, "to_version": to_tag,
            "diff": f"-    image: \"{image}:{from_tag}\"\n+    image: \"{image}:{to_tag}\"",
            "server_commands": [f"sed -i 's|{image}:{from_tag}|{image}:{to_tag}|' {compose_path_on_server}", f"docker compose -f {compose_path_on_server} pull {service}",
                                f"docker compose -f {compose_path_on_server} up -d {service}", f"docker ps --format '{{{{.Names}}}} {{{{.Image}}}}' | grep {service}"],
            "rollback": [f"sed -i 's|{image}:{to_tag}|{image}:{from_tag}|' {compose_path_on_server}", f"docker compose -f {compose_path_on_server} up -d {service}"],
            "note": "반자동 — 서버 명령은 사용자가 실행하고 결과를 붙인다. 그 뒤 inventory 를 다시 만들어 버전이 바뀐 것을 확인하고 close --reason patched"}


def execute(p: dict, runner=None) -> dict:
    return {"result": "awaiting-server", "downtime": p["downtime_expected"], "server_commands": p["server_commands"],
            "note": "에이전트는 서버에 들어가지 않는다 — 명령을 사용자가 실행한 뒤 inventory --write 와 close"}
