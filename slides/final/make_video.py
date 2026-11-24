"""把期末簡報做成有 AI 語音旁白的影片（YouTube 用，> 10 分鐘）。

流程：
1. 讀 AirSleuth_期末簡報.pptx 每一頁的備忘稿（講稿）
2. 用 Gemini 語音合成（gemini-3.8-flash-tts）產生每頁的旁白；失敗時改用 Windows 內建雅婷語音
3. 把每段語音轉回文字，和講稿比對，確認沒有漏念或多念（語音模型有時會把指示也念出來）
4. 用 PowerPoint 把語音放進每一頁、依語音長度自動換頁，匯出 1080p MP4

語音檔快取在 slides/final/audio/（講稿沒改就不重做）。上傳 YouTube 由使用者自己操作。

用法（Windows，需要 PowerPoint 與 GEMINI_API_KEY，從專案根目錄）：
    .venv\\Scripts\\python -m slides.final.make_video
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import subprocess
import time
import wave
from difflib import SequenceMatcher
from pathlib import Path

import requests
from pptx import Presentation

from src.agent.llm import api_key

HERE = Path(__file__).resolve().parent
DECK = HERE / "AirSleuth_期末簡報.pptx"
NARRATED = HERE / "AirSleuth_期末簡報_旁白.pptx"
VIDEO = HERE / "AirSleuth_期末報告影片.mp4"
AUDIO = HERE / "audio"
TTS_MODEL = "gemini-3.8-flash-tts"
CHECK_MODEL = "gemini-3.5-flash-lite"
VOICE = "Kore"
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def clean(text: str) -> str:
    """念稿用：拿掉多餘空白；英文名稱保持原樣。"""
    return re.sub(r"\s+", "", text.replace("\n", ""))


def gemini_tts(text: str, out: Path) -> None:
    body = {"contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}}
    for attempt in range(4):
        r = requests.post(URL.format(model=TTS_MODEL), headers={"x-goog-api-key": api_key()}, json=body, timeout=180)
        if r.ok:
            data = base64.b64decode(r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
            if data[:4] != b"RIFF":  # 舊版模型回傳 24 kHz 16-bit PCM，自己加 WAV 檔頭
                with wave.open(str(out), "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(24000)
                    w.writeframes(data)
            else:
                out.write_bytes(data)
            return
        if r.status_code in (429, 500, 503):
            time.sleep(30 * (attempt + 1))
            continue
        raise RuntimeError(f"TTS HTTP {r.status_code}: {r.text[:200]}")
    raise RuntimeError("TTS 一直失敗")


def windows_tts(text: str, out: Path) -> None:
    """備援：Windows 內建 SAPI 的繁體中文語音（曉涵）。腳本存成 UTF-8（含 BOM）再執行，中文才不會亂碼。"""
    script = AUDIO / "_tts.ps1"
    script.parent.mkdir(exist_ok=True)
    script.write_text(f"""Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('Microsoft Hanhan Desktop')
$s.Rate = 1
$s.SetOutputToWaveFile('{out}')
$s.Speak(@'
{text}
'@)
$s.Dispose()
""", encoding="utf-8-sig")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)], check=True,
                   capture_output=True)


def duration(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def transcript(path: Path) -> str:
    body = {"contents": [{"parts": [{"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(path.read_bytes()).decode()}},
                                    {"text": "請逐字轉錄這段音訊（繁體中文），只輸出轉錄文字，不要加空格。"}]}]}
    r = requests.post(URL.format(model=CHECK_MODEL), headers={"x-goog-api-key": api_key()}, json=body, timeout=180)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def similarity(a: str, b: str) -> float:
    """講稿和轉錄文字的相似度。轉錄常把「二零二五」寫成「2025」，所以先去掉數字（國字與阿拉伯數字）與標點再比。"""
    norm = lambda s: re.sub(r"[\s，。、；：！？「」（）,.;:!?()\-0-9零一二三四五六七八九十百千萬兩點]", "", s).lower()  # noqa: E731
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def make_audio() -> list[dict]:
    AUDIO.mkdir(exist_ok=True)
    prs = Presentation(str(DECK))
    report = []
    for i, slide in enumerate(prs.slides, 1):
        text = clean(slide.notes_slide.notes_text_frame.text)
        out = AUDIO / f"{i:02d}.wav"
        meta_path = AUDIO / f"{i:02d}.json"
        digest = hashlib.sha256(text.encode()).hexdigest()[:16]
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        if not out.exists() or meta.get("digest") != digest:
            try:
                gemini_tts(text, out)
                engine = TTS_MODEL
            except Exception as exc:  # noqa: BLE001
                print(f"第 {i} 頁 Gemini 語音失敗（{exc}），改用 Windows 雅婷語音")
                windows_tts(text, out)
                engine = "Windows Yating"
            heard = transcript(out)
            meta = {"digest": digest, "engine": engine, "seconds": round(duration(out), 1),
                    "match": round(similarity(text, heard), 3), "heard": heard}
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            time.sleep(6)
        report.append({"slide": i, **{k: meta[k] for k in ("engine", "seconds", "match")}})
        flag = "" if meta["match"] >= 0.85 else "  ← 請檢查"
        print(f"第 {i:2d} 頁：{meta['seconds']:5.1f} 秒｜{meta['engine']}｜與講稿相似度 {meta['match']:.2f}{flag}", flush=True)
    return report


def make_video(report: list[dict]) -> None:
    """用 PowerShell 操作 PowerPoint（COM）：每頁加入語音、依語音長度換頁，再匯出 MP4。"""
    lines = [f"@{{ File = '{AUDIO / f'{x['slide']:02d}.wav'}'; Seconds = {x['seconds'] + 1.0} }}" for x in report]
    script = f"""
$items = @({', '.join(lines)})
$app = New-Object -ComObject PowerPoint.Application
$pres = $app.Presentations.Open('{DECK}', $false, $false, $false)
for ($i = 1; $i -le $items.Count; $i++) {{
    $slide = $pres.Slides.Item($i)
    $shape = $slide.Shapes.AddMediaObject2($items[$i - 1].File, $false, $true, -100, -100, 40, 40)
    $shape.AnimationSettings.PlaySettings.PlayOnEntry = $true
    $shape.AnimationSettings.PlaySettings.HideWhileNotPlaying = $true
    $slide.SlideShowTransition.AdvanceOnTime = $true
    $slide.SlideShowTransition.AdvanceTime = $items[$i - 1].Seconds
}}
$pres.SaveAs('{NARRATED}')
$pres.CreateVideo('{VIDEO}', $true, 5, 1080, 30, 90)
while ($pres.CreateVideoStatus -eq 1 -or $pres.CreateVideoStatus -eq 2) {{ Start-Sleep -Seconds 5 }}
"status=" + $pres.CreateVideoStatus
$pres.Close(); $app.Quit()
"""
    out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=7200)
    total = sum(x["seconds"] + 1.0 for x in report)
    print(out.stdout.strip(), out.stderr.strip()[:500])
    print(f"影片：{VIDEO.name}（3 = 完成），約 {total / 60:.1f} 分鐘")


def main() -> None:
    report = make_audio()
    make_video(report)


if __name__ == "__main__":
    main()
