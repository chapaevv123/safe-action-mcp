from pathlib import Path

ROOT=Path(__file__).parents[1]

def test_submission_assets_complete():
    required=["README.md","LICENSE","docs/security.md","docs/threat-model.md","docs/friction-log.md","docs/product-feedback.md","docs/judging-map.md","submission/video-script-180s.md","submission/devpost-field-map.md"]
    assert all((ROOT/p).is_file() and (ROOT/p).stat().st_size>20 for p in required)

def test_no_real_action_dependencies():
    text="\n".join(p.read_text(encoding="utf-8") for p in (ROOT/"safe_action_mcp").glob("*.py"))
    banned=("boto3","web3","stripe","paypal","requests.post","httpx.post")
    assert not any(token in text.lower() for token in banned)

def test_video_script_under_target_word_budget():
    words=(ROOT/"submission/video-script-180s.md").read_text(encoding="utf-8").split()
    assert len(words)<420
