import os
import requests
import datetime
import google.generativeai as genai

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

    if item["id"]["kind"] != "youtube#video":
        print(f"⚠️ Not a video for {channel_id}")
        return None

    return {
        "video_id": item["id"]["videoId"],
        "title": item["snippet"]["title"],
        "channel": item["snippet"]["channelTitle"],
        "description": item["snippet"]["description"]
    }


# ===== STEP 2: Gemini总结（基于URL）=====
def summarize(video_url, title, description):
    prompt = f"""
这是一个YouTube财经视频：

标题：
{title}

简介：
{description}

视频链接：
{video_url}

请总结视频内容（允许合理推测）：

输出格式：
👉 TL;DR（一句话）
👉 主要内容（3点）
👉 涉及主题（AI / 利率 / TSLA等）

用中文，结构清晰。
"""

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"❌ Gemini error: {e}")
        return "Summary failed"


# ===== STEP 3: 聚合 TLDR =====
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
    except Exception as e:
        print("❌ TLDR failed:", e)
        return "TL;DR生成失败"


# ===== STEP 4: 关键词统计 =====
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
        print(f"\n--- Processing {ch['name']}")

        v = get_latest_video(ch["channel_id"])
        if not v:
            continue

        video_url = f"https://www.youtube.com/watch?v={v['video_id']}"

        summary = summarize(
            video_url,
            v["title"],
            v.get("description", "")
        )

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
    output = f"""## 📊 今日美股市场共识（基于{len(videos)}个头部博主）

📅 {today}

---

## 🔥 TL;DR

{tldr}

---

## 📊 今日话题分布

"""

    for k, v in topics.items():
        output += f"- {k}: {v}\n"

    output += "\n---\n\n## 🎥 今日精选视频\n\n"

    for i, v in enumerate(videos):
        output += f"""### 🎥 {i+1}. {v['title']}｜{v['channel']}

{v['summary']}

🔗 https://www.youtube.com/watch?v={v['video_id']}

---

"""

    with open("output.md", "w") as f:
        f.write(output)

    print("\n✅ Generated output:\n")
    print(output)


if __name__ == "__main__":
    main()
