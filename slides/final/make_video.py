"""把期末簡報做成有 AI 語音旁白的影片（YouTube 用，> 10 分鐘）。

流程：
1. 讀 AirSleuth_期末簡報.pptx 每一頁的備忘稿（講稿）
2. 用 Gemini 語音合成（gemini-3.8-flash-tts）產生每頁的旁白
3. 把每段語音轉回文字，和講稿比對，確認沒有漏念或多念（語音模型有時會把指示也念出來）
4. 用 PowerPoint 把語音放進每一頁、依語音長度自動換頁，匯出 1080p MP4

整支影片只用同一個聲音：Gemini 語音失敗（例如免費額度用完）就停下，不會中途換成別的聲音。
語音檔快取在 slides/final/audio/（講稿沒改就不重做），所以重跑會從失敗的那一頁接續。
免費額度是每個專案每天各自計算（語音模型每天 10 次）。組員提供自己的 key 時，放在 .env 的
GEMINI_API_KEY_2、GEMINI_API_KEY_3…：前一把當天用完就換下一把，模型和聲音不變。
加 --windows 則全部改用 Windows 內建語音（Microsoft Hanhan）。上傳 YouTube 由使用者自己操作。

用法（Windows，需要 PowerPoint 與 GEMINI_API_KEY，從專案根目錄）：
    .venv\\Scripts\\python -m slides.final.make_video [--windows]
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import time
import wave
from difflib import SequenceMatcher
from pathlib import Path

import requests
from dotenv import load_dotenv
from pptx import Presentation

from src.agent.llm import ROOT

HERE = Path(__file__).resolve().parent
DECK = HERE / "AirSleuth_期末簡報.pptx"
NARRATED = HERE / "AirSleuth_期末簡報_旁白.pptx"
VIDEO = HERE / "AirSleuth_期末報告影片.mp4"
AUDIO = HERE / "audio"
TTS_MODEL = "gemini-3.8-flash-tts"
CHECK_MODEL = "gemini-3.5-flash-lite"
VOICE = "Kore"
WINDOWS_ENGINE = "Windows Hanhan"
TTS_GAP = 21  # 兩次語音請求至少隔幾秒（免費額度每分鐘最多約 3 次）
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def api_keys() -> list[str]:
    """GEMINI_API_KEY，再加上組員提供的 GEMINI_API_KEY_2～_9（環境變數或 .env），去掉空的和重複的。"""
    load_dotenv(ROOT / ".env")
    names = ["GEMINI_API_KEY"] + [f"GEMINI_API_KEY_{n}" for n in range(2, 10)]
    values = [os.environ.get(n, "").strip() for n in names]
    keys = list(dict.fromkeys(v for v in values if v))
    if not keys:
        raise RuntimeError("沒有設定 GEMINI_API_KEY")
    return keys


def clean(text: str) -> str:
    """念稿用：拿掉換行和空白（英文名稱也會連在一起，例如 AirSleuth；實測轉錄確認念法正確）。"""
    return re.sub(r"\s+", "", text.replace("\n", ""))


def quota_info(r: requests.Response) -> tuple[list[str], float | None]:
    """429 回應裡被超過的配額（名稱=上限）與建議等待秒數。"""
    try:
        details = r.json().get("error", {}).get("details", [])
    except ValueError:
        return [], None
    quotas, delay = [], None
    for d in details:
        quotas += [f"{v.get('quotaId')}={v.get('quotaValue')}" for v in d.get("violations", [])]
        try:
            delay = float(str(d["retryDelay"]).rstrip("s"))
        except (KeyError, ValueError):
            pass
    return quotas, delay


_last_tts = 0.0
_key = 0  # 語音目前用第幾把 key（從 0 算）；當天額度用完就換下一把，這次執行不再換回來


def gemini_tts(text: str, out: Path) -> None:
    global _last_tts, _key
    keys = api_keys()
    body = {"contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}}
    attempt = 0
    while attempt < 5:
        time.sleep(max(0.0, TTS_GAP - (time.time() - _last_tts)))  # 免費額度每分鐘的請求數有限
        _last_tts = time.time()
        r = requests.post(URL.format(model=TTS_MODEL), headers={"x-goog-api-key": keys[_key]}, json=body, timeout=180)
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
        if r.status_code == 429:
            quotas, delay = quota_info(r)
            if quotas and all("PerDay" in q for q in quotas):
                if _key + 1 < len(keys):  # 換下一把 key，不算一次失敗
                    _key += 1
                    print(f"  第 {_key} 把 key 今天的語音額度已用完，改用第 {_key + 1} 把", flush=True)
                    continue
                raise RuntimeError(f"{len(keys)} 把 key 今天的免費額度都已用完（{'、'.join(quotas)}；"
                                   "每日額度在美西時間午夜重置，也就是台灣時間 16:00）")
            wait = delay if delay is not None else 30 * (attempt + 1)
            print(f"  語音模型限流（{'、'.join(quotas) or '未說明'}），等 {wait:.0f} 秒再試", flush=True)
            time.sleep(wait + 2)
        elif r.status_code in (500, 503):
            time.sleep(30 * (attempt + 1))
        else:
            raise RuntimeError(f"TTS HTTP {r.status_code}: {r.text[:200]}")
        attempt += 1
    raise RuntimeError("TTS 一直失敗")


def windows_tts(text: str, out: Path) -> None:
    """--windows 用：Windows 內建 SAPI 的繁體中文語音（Microsoft Hanhan）。腳本存成 UTF-8（含 BOM）再執行，中文才不會亂碼。"""
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


def normalize(text: str) -> str:
    """比對用：轉錄常把「二零二五」寫成「2025」，所以去掉數字（國字與阿拉伯數字）、標點和空白。"""
    text = text.replace("百分之", "")  # 「百分之五十」常被寫成「50%」
    return re.sub(r"[\s，。、；：！？「」（）,.;:!?()%％\-0-9零一二三四五六七八九十百千萬兩點]", "", text).lower()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b), autojunk=False).ratio()


def transcript(path: Path, expected: str, tries: int = 5) -> str | None:
    """把語音轉回文字核對。轉錄模型偶爾忙碌（503），或只回前幾個字就停，所以結果太短也重試，留最完整的一次；
    全部失敗就回傳 None（不核對，但不中斷整支影片）。有多把 key 時輪流用，其中一把額度用完也還能核對。"""
    keys = api_keys()
    body = {"contents": [{"parts": [{"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(path.read_bytes()).decode()}},
                                    {"text": "請逐字轉錄這段音訊。中文寫成繁體中文；念到英文名稱時照英文拼寫寫出來。只輸出轉錄文字。"}]}]}
    best = None
    for attempt in range(tries):
        try:
            r = requests.post(URL.format(model=CHECK_MODEL), headers={"x-goog-api-key": keys[attempt % len(keys)]},
                              json=body, timeout=180)
        except requests.RequestException:
            r = None
        if r is not None and r.ok:
            parts = r.json()["candidates"][0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            if best is None or len(text) > len(best):
                best = text
            if len(normalize(best)) >= 0.9 * len(normalize(expected)):
                return best
        time.sleep(15 * (attempt + 1))
    return best


def make_audio(windows: bool = False) -> list[dict]:
    AUDIO.mkdir(exist_ok=True)
    prs = Presentation(str(DECK))
    engine = WINDOWS_ENGINE if windows else TTS_MODEL
    report = []
    for i, slide in enumerate(prs.slides, 1):
        text = clean(slide.notes_slide.notes_text_frame.text)
        out = AUDIO / f"{i:02d}.wav"
        meta_path = AUDIO / f"{i:02d}.json"
        digest = hashlib.sha256(text.encode()).hexdigest()[:16]
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        if not out.exists() or meta.get("digest") != digest or meta.get("engine") != engine:
            if windows:
                windows_tts(text, out)
            else:
                try:
                    gemini_tts(text, out)
                except Exception as exc:  # noqa: BLE001
                    raise SystemExit(f"第 {i} 頁 Gemini 語音失敗：{exc}\n前 {i - 1} 頁的語音已存在 {AUDIO}，"
                                     "稍後重跑會從這一頁接續；或加 --windows 全部改用 Windows 語音。") from exc
            meta = {"digest": digest, "engine": engine, "seconds": round(duration(out), 1), "heard": None}
            time.sleep(6)
        # 還沒轉錄、或轉錄和講稿差很多時再轉錄一次（不用重做語音），留比較接近講稿的那一次
        if meta.get("heard") is None or similarity(text, meta["heard"]) < 0.85:
            heard = transcript(out, text)
            if heard is not None and (meta.get("heard") is None or similarity(text, heard) > similarity(text, meta["heard"])):
                meta["heard"] = heard
        meta["match"] = None if meta.get("heard") is None else round(similarity(text, meta["heard"]), 3)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        report.append({"slide": i, **{k: meta[k] for k in ("engine", "seconds", "match")}})
        if meta["match"] is None:
            check = "未核對（轉錄服務忙碌）  ← 請檢查"
        else:
            check = f"與講稿相似度 {meta['match']:.2f}" + ("" if meta["match"] >= 0.85 else "  ← 請檢查")
        print(f"第 {i:2d} 頁：{meta['seconds']:5.1f} 秒｜{meta['engine']}｜{check}", flush=True)
    return report


def make_video(report: list[dict]) -> None:
    """用 PowerShell 操作 PowerPoint（COM）：每頁加入語音、依語音長度換頁，再匯出 MP4。
    PowerPoint 只會有一個執行個體；如果使用者已經開著，就在同一個程式裡開這份簡報（不顯示視窗），做完只關這份。"""
    lines = [f"@{{ File = '{AUDIO / f'{x['slide']:02d}.wav'}'; Seconds = {x['seconds'] + 1.0} }}" for x in report]
    script = f"""
$items = @({', '.join(lines)})
$wasRunning = [bool](Get-Process POWERPNT -ErrorAction SilentlyContinue)
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
$pres.Close()
if (-not $wasRunning) {{ $app.Quit() }}  # 使用者原本就開著 PowerPoint 時不關掉，以免關掉他正在用的簡報
"""
    VIDEO.unlink(missing_ok=True)  # 舊的影片先刪掉，避免匯出失敗時誤把舊檔當成新檔
    out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=7200)
    total = sum(x["seconds"] + 1.0 for x in report)
    print(out.stdout.strip(), out.stderr.strip()[:500])
    print(f"影片：{VIDEO.name}（3 = 完成），約 {total / 60:.1f} 分鐘", flush=True)


def video_info(path: Path) -> dict:
    """不用 ffmpeg 讀 MP4 的 moov：影片長度（秒）和有沒有音軌（hdlr 'soun'）。"""
    with path.open("rb") as f:
        while True:
            head = f.read(8)
            if len(head) < 8:
                return {}
            size, kind = struct.unpack(">I4s", head)
            header = 8
            if size == 1:
                size, header = struct.unpack(">Q", f.read(8))[0], 16
            if kind == b"moov":
                moov = f.read(size - header) if size else f.read()
                break
            if size == 0:
                return {}
            f.seek(size - header, 1)
    i = moov.find(b"mvhd")
    if i < 0:
        return {}
    if moov[i + 4] == 1:
        timescale, length = struct.unpack(">IQ", moov[i + 24:i + 36])
    else:
        timescale, length = struct.unpack(">II", moov[i + 16:i + 24])
    return {"seconds": length / timescale, "audio": b"soun" in moov}


def main() -> None:
    windows = "--windows" in sys.argv[1:]
    if not windows:
        print(f"語音用的 Gemini key：{len(api_keys())} 把", flush=True)
    report = make_audio(windows=windows)
    make_video(report)
    info = video_info(VIDEO) if VIDEO.exists() else {}
    if info:
        print(f"檢查影片：長度 {info['seconds'] / 60:.1f} 分鐘，{'有' if info['audio'] else '沒有'}音軌", flush=True)
    else:
        print("檢查影片：找不到影片或讀不到長度，匯出可能失敗", flush=True)


if __name__ == "__main__":
    main()
