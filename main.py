import os
import requests
from youtube_transcript_api import YouTubeTranscriptApi
import datetime
import google.generativeai as genai

# ====== CONFIG ======
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

CHANNEL_IDS = [
    "UC_xxx1",
    "UC_xxx2",
    "UC_xxx3",
    "UC_xxx4",
    "UC_xxx5",
]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ====== STEP 1: GET LATEST VIDEOS ======
def get_latest_video(channel_id):
    url = f"https://www.googleapis.com/youtube/v3/search?key={YOUTUBE_API_KEY}&channelId={channel_id}&part=snippet&order=date&maxResults=1"
    res = requests.get(url).json()

    item = res["items"][0]
    return {
        "video_id": item["id"]["videoId"],
        "title": item["snippet"]["title"],
        "channel": item["snippet"]["channelTitle"]
    }

# ====== STEP 2: GET TRANSCRIPT ======
def get_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([x['text'] for x in transcript])
    except:
        return None

# ====== STEP 3: SUMMARY ======
def summarize(text):
    prompt = f"""
请总结以下YouTube财经视频：

输出：
1. 一句话TL;DR
2. 3个要点
3. 涉及主题（如AI/利率/TSLA）

内容：
{text[:4000]}
"""
    response = model.generate_content(prompt)
    return response.text

# ====== STEP 4: TLDR AGGREGATION ======
def aggregate_tldr(all_summaries):
    prompt = f"""
基于以下多个视频总结，提炼3条“市场共识”：

要求：
- 不加入主观判断
- 每条一句话
- 中文

内容：
{all_summaries}
"""
    response = model.generate_content(prompt)
    return response.text

# ====== STEP 5: TOPIC COUNT ======
def topic_count(all_summaries):
    keywords = {
        "AI": ["ai", "nvidia"],
        "利率": ["rate", "fed", "inflation"],
        "TSLA": ["tesla"],
    }

    counts = {k: 0 for k in keywords}

    for summary in all_summaries.lower().split():
        for topic, keys in keywords.items():
            if any(k in summary for k in keys):
                counts[topic] += 1

    return counts

# ====== MAIN ======
def main():
    videos = []

    for ch in CHANNEL_IDS:
        v = get_latest_video(ch)
        transcript = get_transcript(v["video_id"])

        if transcript:
            summary = summarize(transcript)
            v["summary"] = summary
            videos.append(v)

    # merge summaries
    all_text = "\n\n".join([v["summary"] for v in videos])

    tldr = aggregate_tldr(all_text)
    topic_stats = topic_count(all_text)

    today = datetime.date.today()

    # ===== OUTPUT MARKDOWN =====
    output = f"""## 📊 今日美股市场共识（基于5个头部博主）

📅 {today}

---

## 🔥 TL;DR

{tldr}

---

## 📊 今日话题分布

"""
    for k, v in topic_stats.items():
        output += f"- {k}: {v}\n"

    output += "\n---\n\n## 🎥 今日精选视频（5条）\n\n"

    for i, v in enumerate(videos):
        output += f"""### 🎥 {i+1}. {v['title']}｜{v['channel']}

{v['summary']}

---

"""

    # save file
    with open("output.md", "w") as f:
        f.write(output)

    print(output)


if __name__ == "__main__":
    main()
