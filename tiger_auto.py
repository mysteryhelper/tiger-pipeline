import os, asyncio, datetime, re, pickle, random, textwrap, time, shutil
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from moviepy.editor import *
from moviepy.video.fx.all import resize, crop
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from duckduckgo_search import DDGS
import google.generativeai as genai
import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import schedule

# Market research
try:
    from pytrends.request import TrendReq
    PYTENDS_AVAILABLE = True
except:
    PYTENDS_AVAILABLE = False

# ================== 🎯 CHANNEL CONFIG ==================
CHANNEL_NAME = "Future AI Toolkit"
PRIVACY = "private" # test ke baad "public"
RESOLUTION = (1920, 1080)
FPS = 30
INTRO_DURATION = 3
OUTRO_DURATION = 8
DISCLAIMER = "\n\n⚠️ Disclaimer: This video is for educational purposes only. Not financial advice.\n"
# 👇 Linux paths (Ubuntu GitHub Actions)
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
PROFILE_PIC = "assets/profile.png"

PEXELS_KEY = os.getenv("PEXELS_API_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]
CREDENTIALS_FILE = "client_secrets.json"
TOKEN_FILE = "token.pickle"
VIDEO_CATEGORY = "27"

# ================== ASSET GENERATION ==================
def get_profile_clip(size=(120,120)):
    if os.path.exists(PROFILE_PIC):
        img = Image.open(PROFILE_PIC).resize(size)
        mask = Image.new("L", size, 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, size[0], size[1]), fill=255)
        img.putalpha(mask)
        return ImageClip(np.array(img))
    else:
        initials = ''.join(word[0].upper() for word in CHANNEL_NAME.split()[:2])
        img = Image.new("RGBA", size, (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((2,2,size[0]-2,size[1]-2), fill=(50,50,50,255))
        font = ImageFont.truetype(FONT_BOLD, 50)
        draw.text((size[0]//2, size[1]//2), initials, fill="white", font=font, anchor="mm")
        return ImageClip(np.array(img))

def create_intro():
    profile = get_profile_clip((120,120)).set_position((40,40)).set_duration(INTRO_DURATION)
    txt = TextClip(CHANNEL_NAME, fontsize=80, font=FONT_BOLD, color='white',
                   stroke_color='black', stroke_width=3)
    txt = txt.set_position('center').set_duration(INTRO_DURATION).crossfadein(0.5).crossfadeout(0.5)
    bg = ColorClip(RESOLUTION, color=(10, 40, 30)).set_duration(INTRO_DURATION)
    intro = CompositeVideoClip([bg, txt, profile])
    intro.write_videofile("assets/intro.mp4", fps=FPS, logger=None)

def create_outro():
    profile = get_profile_clip((100,100)).set_position((RESOLUTION[0]//2 - 50, 300)).set_duration(OUTRO_DURATION)
    txt = TextClip("Subscribe for more!", fontsize=70, font=FONT_BOLD, color='white',
                   stroke_color='black', stroke_width=3)
    txt = txt.set_position(('center', 450)).set_duration(OUTRO_DURATION).crossfadein(0.5).crossfadeout(0.5)
    bg = ColorClip(RESOLUTION, color=(10, 40, 30)).set_duration(OUTRO_DURATION)
    outro = CompositeVideoClip([bg, txt, profile])
    outro.write_videofile("assets/outro.mp4", fps=FPS, logger=None)

def create_thumbnail_base():
    img = Image.new('RGB', (1280, 720), color=(20, 60, 40))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_BOLD, 50)
    draw.text((40, 40), CHANNEL_NAME, fill="gold", font=font, stroke_width=2, stroke_fill="black")
    if os.path.exists(PROFILE_PIC):
        avatar = Image.open(PROFILE_PIC).resize((80,80))
        mask = Image.new("L", (80,80), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0,0,80,80), fill=255)
        avatar.putalpha(mask)
        img.paste(avatar, (1100, 40), avatar)
    img.save("assets/thumbnail_base.png")

def ensure_assets():
    if not os.path.exists("assets"):
        os.makedirs("assets")
    if not os.path.exists("assets/fonts"):
        os.makedirs("assets/fonts")
    if not os.path.exists("assets/intro.mp4"):
        create_intro()
    if not os.path.exists("assets/outro.mp4"):
        create_outro()
    if not os.path.exists("assets/thumbnail_base.png"):
        create_thumbnail_base()

# ================== THUMBNAIL ==================
def create_thumbnail(title, hook_text="", output_path="thumbnail.jpg"):
    base = Image.open("assets/thumbnail_base.png")
    draw = ImageDraw.Draw(base)
    font = ImageFont.truetype(FONT_BOLD, 60)
    if hook_text:
        lines = textwrap.wrap(hook_text, width=20)
        y = 150
        for line in lines:
            draw.text((60, y), line, fill="white", font=font, stroke_width=2, stroke_fill="black")
            y += 70
    title_lines = textwrap.wrap(title, width=30)
    y = 500
    for line in title_lines:
        draw.text((60, y), line, fill="yellow", font=font, stroke_width=2, stroke_fill="black")
        y += 70
    base.save(output_path)
    return output_path

# ================== WEB SEARCH ==================
def web_search(query, max_results=8):
    try:
        with DDGS() as ddgs:
            results = []
            for r in ddgs.text(query, max_results=max_results):
                results.append(r['body'])
            return "\n".join(results)
    except Exception as e:
        print(f"Web search failed: {e}. Using offline facts.")
        return f"Finance tips for {query}."

# ================== MARKET RESEARCH ==================
def get_trending_queries(keyword, timeframe='today 3-m'):
    if not PYTENDS_AVAILABLE:
        return []
    for attempt in range(3):
        try:
            pytrend = TrendReq(hl='en-US', tz=360, timeout=(10,25))
            pytrend.build_payload([keyword], cat=0, timeframe=timeframe, geo='US', gprop='youtube')
            related = pytrend.related_queries()
            rising = related[keyword]['rising'] if keyword in related and related[keyword]['rising'] is not None else []
            return rising['query'].tolist() if not rising.empty else []
        except Exception as e:
            if "429" in str(e):
                wait = 60 * (attempt + 1)
                print(f"Google Trends rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"Trends error: {e}")
                return []
    return []

def competitor_titles(topic):
    query = f'"{topic}" YouTube video title best guide 2026'
    search_text = web_search(query, 5)
    titles = re.findall(r'(?:"([^"]+)"|([A-Z][^.]*?(?:2026|credit card|ETF|invest)))', search_text)
    titles = [t[0] if t[0] else t[1] for t in titles if any(t)]
    return list(set([t.strip() for t in titles if len(t.strip()) > 20]))[:5]

def market_research(topic):
    trends = get_trending_queries(topic.split()[0])
    comp_titles = competitor_titles(topic)
    return {"trends": trends, "competitor_titles": comp_titles}

# ================== SEO METADATA GENERATOR ==================
def generate_seo_metadata(script_text, topic, research_data):
    trend_list = research_data.get('trends', [])
    comp_titles = research_data.get('competitor_titles', [])
    research_str = f"Trending keywords: {', '.join(trend_list)}\nTop competitor titles: {', '.join(comp_titles)}"
    prompt = (
        "You are a YouTube SEO expert for a finance channel. Based on the script and market research, create a viral-optimized metadata package.\n\n"
        f"Script (excerpt): {script_text[:1000]}\n"
        f"Topic: {topic}\n"
        f"Research: {research_str}\n\n"
        "Rules:\n"
        "1. Title: Must include a number, power word (e.g., 'Secret', 'Ultimate', 'Shocking'), and the current year (2026). Keep under 60 characters.\n"
        "2. Description: Write a 2-3 sentence description using keywords naturally. Include CTA and disclaimer.\n"
        "3. Tags: Provide 10-15 relevant tags, including long-tail keywords.\n\n"
        "Output format:\n"
        "TITLE: <title>\n"
        "DESCRIPTION: <description>\n"
        "TAGS: tag1, tag2, tag3..."
    )
    models = ["gemini-2.0-flash", "gemini-1.5-flash-latest", "gemini-1.0-pro"]
    if GEMINI_KEY:
        for model_name in models:
            try:
                model = genai.GenerativeModel(model_name)
                resp = model.generate_content(prompt)
                return resp.text
            except:
                continue
    return f"TITLE: {topic} (2026) – Top Tips & Secrets\nDESCRIPTION: Discover the latest insights on {topic}. Subscribe for more finance content.\nTAGS: {topic}, finance, 2026, money, tips"

def parse_seo_output(seo_text):
    title = desc = ""
    tags = []
    lines = seo_text.split('\n')
    mode = None
    desc_lines = []
    for line in lines:
        if line.startswith("TITLE:"):
            title = line[6:].strip()
        elif line.startswith("DESCRIPTION:"):
            mode = "desc"
            desc_lines.append(line[12:].strip())
        elif line.startswith("TAGS:"):
            if mode == "desc":
                desc = " ".join(desc_lines)
                mode = None
            tags = [t.strip() for t in line[5:].split(",")]
        else:
            if mode == "desc":
                desc_lines.append(line.strip())
    if mode == "desc":
        desc = " ".join(desc_lines)
    return title, desc, tags

# ================== SCRIPT GENERATION (Gemini only) ==================
def generate_script_gemini(topic, facts_text, research_data):
    research_str = f"Trending: {', '.join(research_data.get('trends', []))}\nCompetitors: {', '.join(research_data.get('competitor_titles', []))}"
    models = ["gemini-2.0-flash", "gemini-1.5-flash-latest", "gemini-1.0-pro"]
    for model_name in models:
        for attempt in range(2):
            try:
                print(f"Trying Gemini {model_name} (attempt {attempt+1})")
                model = genai.GenerativeModel(model_name)
                prompt = f"""You are a top US finance YouTuber. Write a script for: "{topic}".
Market Research: {research_str[:500]}
Facts: {facts_text[:1500]}

Structure:
HOOK: (shocking question/stat)
POINT 1: (one clear idea)
BROLL: (3 keywords for stock footage, comma separated)
TEXT: (bold text overlay for this point)
POINT 2: ...
...
CONCLUSION: (summary + CTA to subscribe)

Rules:
- Keep whole script under 600 words.
- Use simple, engaging English.
- Include "{DISCLAIMER}" at the end.
- Mark each section clearly with the labels exactly as shown.
"""
                response = model.generate_content(prompt)
                print(f"✅ Script by Gemini: {model_name}")
                return response.text
            except Exception as e:
                err = str(e)
                if "ResourceExhausted" in err or "429" in err:
                    wait = 30 * (attempt + 1)
                    print(f"Quota exhausted, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"Gemini error: {err[:100]}")
                    break
    return None

def generate_fallback_script(topic, facts_text, research_data):
    facts = facts_text.split('\n')
    points = [f.strip() for f in facts if len(f.strip()) > 50][:5]
    script = f"HOOK: Today we are talking about {topic}. Let's find out the key facts!\n"
    for i, point in enumerate(points, 1):
        script += f"POINT {i}: {point[:200]}\n"
        script += f"BROLL: finance, money, charts\n"
        script += f"TEXT: {point[:80]}\n"
    script += f"CONCLUSION: That's all for {topic}. Subscribe for more finance updates.\n"
    script += DISCLAIMER
    print("⚠️ Using fallback script (no AI).")
    return script

def generate_script(topic, research_data):
    facts = web_search(f"latest {topic} 2026 USA finance guide")
    gemini_script = generate_script_gemini(topic, facts, research_data)
    if gemini_script:
        return gemini_script
    return generate_fallback_script(topic, facts, research_data)

# ================== PARSING ==================
def parse_script(script_text):
    parts = []
    lines = script_text.split('\n')
    current_point = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r'^HOOK\s*:', line, re.I):
            text = re.split(r'\s*:\s*', line, maxsplit=1)[1]
            parts.append({"type": "hook", "text": text.strip()})
        elif re.match(r'^POINT\s*\d*', line, re.I):
            if current_point:
                parts.append(current_point)
            if ':' in line:
                text = re.split(r'\s*:\s*', line, maxsplit=1)[1]
            else:
                text = ''
            current_point = {"type": "point", "text": text.strip(), "broll": [], "text_overlay": ""}
        elif re.match(r'^BROLL\s*:', line, re.I) and current_point is not None:
            keywords = re.split(r'\s*:\s*', line, maxsplit=1)[1]
            current_point['broll'] = [k.strip() for k in keywords.split(',') if k.strip()]
        elif re.match(r'^TEXT\s*:', line, re.I) and current_point is not None:
            current_point['text_overlay'] = re.split(r'\s*:\s*', line, maxsplit=1)[1].strip()
        elif re.match(r'^CONCLUSION\s*:', line, re.I):
            if current_point:
                parts.append(current_point)
                current_point = None
            text = re.split(r'\s*:\s*', line, maxsplit=1)[1]
            parts.append({"type": "conclusion", "text": text.strip()})
    if current_point:
        parts.append(current_point)
    return parts

# ================== TTS (with fallback) ==================
async def generate_tts(text, voice="en-US-ChristopherNeural", output="temp_audio.mp3"):
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output)
        return output
    except Exception as e:
        print(f"❌ edge-tts failed: {e}. Generating silent audio as fallback.")
        word_count = len(text.split())
        duration = max(5, word_count / 150 * 60)
        clip = AudioClip(lambda t: [0, 0], duration=duration, fps=44100)
        clip.write_audiofile(output, logger=None)
        return output

# ================== STOCK FOOTAGE (Pexels) ==================
def download_stock_clips_pexels(keywords, output_dir="temp_broll"):
    os.makedirs(output_dir, exist_ok=True)
    headers = {"Authorization": PEXELS_KEY}
    clips = []
    for kw in keywords:
        resp = requests.get(f"https://api.pexels.com/videos/search?query={kw}&per_page=2&size=large", headers=headers)
        if resp.status_code != 200:
            continue
        for video in resp.json().get('videos', []):
            for file in video['video_files']:
                if file['width'] >= 1920:
                    url = file['link']
                    fname = f"{output_dir}/{kw.replace(' ', '_')}.mp4"
                    if not os.path.exists(fname):
                        r = requests.get(url)
                        with open(fname, 'wb') as f:
                            f.write(r.content)
                    clips.append(fname)
                    break
    return clips

# ================== VIDEO ASSEMBLY ==================
def build_video(parsed_script, audio_path, broll_clips, output="final_video.mp4"):
    intro = VideoFileClip("assets/intro.mp4").resize(RESOLUTION)
    outro = VideoFileClip("assets/outro.mp4").resize(RESOLUTION)
    voice = AudioFileClip(audio_path)
    total_audio_dur = voice.duration
    available_clips = []
    for path in broll_clips:
        try:
            clip = VideoFileClip(path).without_audio().resize(RESOLUTION)
            available_clips.append(clip)
        except:
            continue
    if not available_clips:
        bg = ColorClip(RESOLUTION, (0,0,0)).set_duration(total_audio_dur)
        available_clips = [bg]
    loop_parts = []
    acc_dur = 0
    while acc_dur < total_audio_dur:
        for cl in available_clips:
            loop_parts.append(cl)
            acc_dur += cl.duration
            if acc_dur >= total_audio_dur:
                break
    long_broll = concatenate_videoclips(loop_parts).subclip(0, total_audio_dur).resize(RESOLUTION)
    sections = []
    for part in parsed_script:
        if part['type'] in ['hook', 'point', 'conclusion']:
            sections.append(part)
    total_chars = sum(len(part['text']) for part in sections) or 1
    time_pos = 0
    text_clips = []
    for part in sections:
        part_duration = (len(part['text']) / total_chars) * total_audio_dur
        if part.get('text_overlay') and part['text_overlay'].strip():
            overlay = TextClip(part['text_overlay'], fontsize=55, font=FONT_BOLD,
                               color='white', stroke_color='black', stroke_width=2,
                               method='caption', size=(1700, None))
            overlay = overlay.set_position(('center', 0.8), relative=True).set_start(time_pos).set_duration(part_duration).crossfadein(0.3)
            text_clips.append(overlay)
        time_pos += part_duration
    content_video = CompositeVideoClip([long_broll] + text_clips).set_duration(total_audio_dur)
    final = concatenate_videoclips([intro, content_video, outro])
    audio_content = CompositeAudioClip([voice.set_start(INTRO_DURATION)])
    final = final.set_audio(audio_content)
    final.write_videofile(output, codec="libx264", audio_codec="aac", fps=FPS, logger=None)
    return output

# ================== YOUTUBE UPLOAD ==================
def get_authenticated_service():
    credentials = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            credentials = pickle.load(token)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            credentials = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(credentials, token)
    return build('youtube', 'v3', credentials=credentials)

def upload_video(video_file, title, description, tags, thumbnail_file=None):
    youtube = get_authenticated_service()
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': VIDEO_CATEGORY
        },
        'status': {
            'privacyStatus': PRIVACY,
            'selfDeclaredMadeForKids': False,
        }
    }
    media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    video_id = response['id']
    if thumbnail_file:
        youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumbnail_file)).execute()
    print(f"Uploaded: https://youtu.be/{video_id}")
    return video_id

# ================== MAIN PIPELINE ==================
async def create_and_upload_video(topic):
    print("🔍 Performing market research...")
    research_data = market_research(topic)
    print(f" Trends: {research_data['trends'][:3]}...")
    print(f" Competitors: {research_data['competitor_titles'][:2]}...")

    print("Generating script...")
    raw_script = generate_script(topic, research_data)
    parsed = parse_script(raw_script)
    if not parsed:
        print("❌ Parsing failed, using fallback.")
        facts = web_search(f"latest {topic} 2026 USA finance guide")
        raw_script = generate_fallback_script(topic, facts, research_data)
        parsed = parse_script(raw_script)

    print("🎯 Generating SEO metadata...")
    full_narration = " ".join([p['text'] for p in parsed if p['type'] in ['hook','point','conclusion']]) + DISCLAIMER
    seo_raw = generate_seo_metadata(full_narration, topic, research_data)
    seo_title, seo_desc, seo_tags = parse_seo_output(seo_raw)
    if not seo_title:
        seo_title = f"{topic} - {datetime.date.today().strftime('%b %d, %Y')}"
    if not seo_desc:
        seo_desc = f"{full_narration[:3000]}\n\n{DISCLAIMER}\n\n#finance #money #investing"
    if not seo_tags:
        seo_tags = [tag.strip() for tag in topic.split()] + ["finance", "credit cards", "investing", "2026"]
    print(f" Title: {seo_title}")

    print("Generating voiceover...")
    audio_file = await generate_tts(full_narration, voice="en-US-ChristopherNeural")

    broll_keywords = []
    for part in parsed:
        if part['type'] == 'point' and part.get('broll'):
            broll_keywords.extend(part['broll'])
    if not broll_keywords:
        broll_keywords = ["finance", "money", "investing"]
    broll_keywords = list(set(broll_keywords))[:5]

    print("Downloading stock clips...")
    clips = download_stock_clips_pexels(broll_keywords)

    print("Assembling video...")
    video_path = "output_video.mp4"
    build_video(parsed, audio_file, clips, video_path)

    hook_line = next((p['text'] for p in parsed if p['type'] == 'hook'), "")
    print("Creating thumbnail...")
    thumb_path = create_thumbnail(seo_title, hook_line)

    print("Uploading to YouTube...")
    upload_video(video_path, seo_title, seo_desc, seo_tags, thumb_path)

    # Cleanup
    os.remove(audio_file)
    if os.path.exists("temp_broll"):
        shutil.rmtree("temp_broll")
    print("Done! Next video tomorrow.")

def run_daily_pipeline():
    ensure_assets()
    topics = [
        "Best Credit Cards Nobody Talks About 2026",
        "Top ETFs for Passive Income 2026",
        "Hidden Credit Card Benefits You Miss",
        "I Bonds vs Treasury Bills - Updated 2026",
        "Roth IRA Secrets for Maximum Growth",
        "Chase Sapphire vs Amex Platinum - Real Comparison",
        "How to Stack Credit Card Rewards Like a Pro",
    ]
    today_topic = topics[datetime.date.today().weekday() % len(topics)]
    asyncio.run(create_and_upload_video(today_topic))

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--manual":
        print("🐯 TIGER manual run – generating one video now...")
        run_daily_pipeline()
        print("✅ Video created. Exiting.")
    else:
        schedule.every().day.at("06:00").do(run_daily_pipeline)
        print("🐯 TIGER auto‑scheduler started. Will run daily at 06:00 AM.")
        print(" To run a single video now, use: python tiger_auto.py --manual")
        while True:
            schedule.run_pending()
            time.sleep(60)
