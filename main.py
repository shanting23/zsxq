import os
import requests
import datetime
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai

# ✅ 从配置读取频道
from config import CHANNELS

# ===== CONFIG =====
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")


# ===== STEP 1: 获取最新视频 =====
def get_latest_video(channel_id):
    url = f"https://www.googleapis.com/youtube/v3/search?key={YOUTUBE_API_KEY}&channelId={channel_id}&part=snippet&order=date&maxResults=1"
    res = requests.get(url).json()

    if not res.get("items"):
        print(f"❌ No video found for {channel_id}")
        return None

    item = res["items"][0]

    # 防止不是视频（playlist/channel）
    if item["id"]["kind"] != "youtube#video":
        print(f"⚠️ Not a video for {channel_id}")
        return None

    return {
        "video_id": item["id"]["videoId"],
        "title": item["snippet"]["title"],
        "channel": item["snippet"]["channelTitle"]
    }


# ===== STEP 2: 获取字幕 =====
def get_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join([x["text"] for x in transcript])
        return text
    except Exception as e:
        print(f"❌ Transcript failed for {video_id}: {e}")
        return None


# ===== STEP 3: 单视频总结 =====
def summarize(text):
    prompt = f"""
请总结以下YouTube财经视频：

输出格式：
👉 TL;DR（一句话）
👉 主要内容（3点）
👉 涉及主题（AI/利率/TSLA等）

内容：
{text[:4000]}
"""
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"❌ Gemini error: {e}")
        return "Summary failed"


# ===== STEP 4: 聚合 TL;DR =====
def aggregate_tldr(all_summaries):
    prompt = f"""
基于以下多个视频总结，提炼3条“市场共识”：

要求：
- 不能加入主观判断
- 只总结共性
- 每条一句话
- 中文输出

内容：
{all_summaries}
"""
    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return "TL;DR failed"


# ===== STEP 5: 关键词统计（简单规则版）======
def topic_count(text):
    keywords = {
        "AI / 半导体": ["ai", "nvidia", "chip"],
        "宏观 / 利率": ["fed", "rate", "inflation"],
        "TSLA": ["tesla"],
    }

    text = text.lower()
    result = {}

    for topic, keys in keywords.items():
        count = sum([text.count(k) for k in keys])
        result[topic] = count

    return result


# ===== MAIN =====
def main():
    videos = []

    print("✅ Loaded channels:", CHANNELS)

    for ch in CHANNELS:
        print(f"--- Processing {ch['name']}")

        v = get_latest_video(ch["channel_id"])
        if not v:
            continue

        transcript = get_transcript(v["video_id"])
        if not transcript:
            continue

        summary = summarize(transcript)

        v["summary"] = summary
        v["channel"] = ch["name"]

        videos.append(v)

    if not videos:
        print("❌ No valid videos found")
        return

    # ===== 聚合 =====
    all_text = "\n\n".join([v["summary"] for v in videos])

    tldr = aggregate_tldr(all_text)
    topics = topic_count(all_text)

    today = datetime.date.today()

    # ===== 输出 =====
    output = f"""## 📊 今日美股市场共识（基于5个头部博主）

📅 {today}

---

## 🔥 TL;DR

{tldr}

---

## 📊 今日话题分布

"""

    for k, v in topics.items():
        output += f"- {k}: {v}\n"

    output += "\n---\n\n## 🎥 今日精选视频（5条）\n\n"

    for i, v in enumerate(videos):
        output += f"""### 🎥 {i+1}. {v['title']}｜{v['channel']}

{v['summary']}

---

"""

    # 保存文件
    with open("output.md", "w") as f:
        f.write(output)

    print("✅ Generated output:")
    print(output)


if __name__ == "__main__":
    main()
