# =============================================================================
# AI STORYBOARD GENERATOR - FULLY FIXED VERSION
# All scenes and audio now properly included in video
# =============================================================================

import os
import json
import asyncio
import nest_asyncio
import edge_tts
from PIL import Image, ImageDraw, ImageFont
import gradio as gr
from groq import Groq
import requests
from io import BytesIO
import time
import urllib.parse
import warnings

warnings.filterwarnings('ignore')
nest_asyncio.apply()

# =============================================================================
# MOVIEPY IMPORT - FIXED FOR COMPATIBILITY
# =============================================================================

try:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip, ColorClip
    print("✅ MoviePy imported successfully")
except ImportError as e:
    print(f"❌ MoviePy import error: {e}")
    raise

# =============================================================================
# GLOBAL STORAGE FOR GENERATED FILES
# =============================================================================

class StoryboardFiles:
    """Class to track all generated files"""
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.images = {}  # {scene_number: path}
        self.audio = {}   # {scene_number: path}
        self.title_card = None
        self.end_card = None
    
    def add_image(self, scene_number, path):
        self.images[scene_number] = path
        print(f"   📁 Stored image for scene {scene_number}: {path}")
    
    def add_audio(self, scene_number, path):
        self.audio[scene_number] = path
        print(f"   📁 Stored audio for scene {scene_number}: {path}")
    
    def get_image(self, scene_number):
        return self.images.get(scene_number)
    
    def get_audio(self, scene_number):
        return self.audio.get(scene_number)
    
    def summary(self):
        print("\n📁 FILES SUMMARY:")
        print(f"   Images: {len(self.images)}")
        for num, path in self.images.items():
            exists = os.path.exists(path) if path else False
            size = os.path.getsize(path) if exists else 0
            print(f"      Scene {num}: {path} (exists: {exists}, size: {size})")
        print(f"   Audio: {len(self.audio)}")
        for num, path in self.audio.items():
            exists = os.path.exists(path) if path else False
            size = os.path.getsize(path) if exists else 0
            print(f"      Scene {num}: {path} (exists: {exists}, size: {size})")

# Global file tracker
files = StoryboardFiles()

# =============================================================================
# API CONFIGURATION
# =============================================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
client = Groq(api_key=GROQ_API_KEY)

print("✅ API configured!")

# =============================================================================
# STORY GENERATOR
# =============================================================================

def generate_consistent_story(user_prompt, num_scenes=4):
    """Generates a story with a VISUAL BIBLE for consistency"""
    
    system_prompt = """You are an expert storyboard artist and writer.
    
    Create a VISUALLY CONSISTENT storyboard where:
    1. Characters look the SAME in every scene
    2. The art style is CONSISTENT throughout
    3. Settings and colors are COHERENT
    
    Return this EXACT JSON format:
    {
        "title": "Story Title",
        "visual_bible": {
            "art_style": "Detailed art style description",
            "color_palette": "Main colors used",
            "main_character": "Detailed character description for EVERY scene",
            "secondary_characters": "Description of other recurring characters",
            "world_setting": "Description of the world/environment"
        },
        "scenes": [
            {
                "scene_number": 1,
                "description": "What happens in this scene",
                "visual_prompt": "Include art_style + character description + scene action + color_palette",
                "narration": "The narration for this scene (2-3 sentences)",
                "camera_angle": "wide shot / close-up / medium shot",
                "mood": "happy / tense / mysterious / etc"
            }
        ]
    }
    
    IMPORTANT: Every visual_prompt MUST include the exact same character description!
    """
    
    user_message = f"""Create a {num_scenes}-scene storyboard for:

    "{user_prompt}"
    
    Return ONLY valid JSON, no other text."""
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.7,
            max_tokens=3000
        )
        
        response_text = chat_completion.choices[0].message.content
        
        # Clean JSON
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        story_data = json.loads(response_text.strip())
        story_data = enhance_visual_prompts(story_data)
        
        return story_data
        
    except Exception as e:
        print(f"Error generating story: {e}")
        return None


def enhance_visual_prompts(story_data):
    """Ensures every scene prompt includes consistent visual elements"""
    
    visual_bible = story_data.get("visual_bible", {})
    
    art_style = visual_bible.get("art_style", "digital art, cinematic")
    color_palette = visual_bible.get("color_palette", "vibrant colors")
    main_character = visual_bible.get("main_character", "")
    
    consistency_prefix = f"{art_style}, {color_palette}"
    
    for scene in story_data.get("scenes", []):
        original_prompt = scene.get("visual_prompt", "")
        
        if main_character and main_character.lower() not in original_prompt.lower():
            enhanced_prompt = f"{main_character}, {original_prompt}"
        else:
            enhanced_prompt = original_prompt
        
        scene["visual_prompt"] = f"{enhanced_prompt}, {consistency_prefix}, consistent character design"
        scene["style_reference"] = consistency_prefix
    
    return story_data


# =============================================================================
# IMAGE GENERATOR
# =============================================================================

def generate_image(prompt, scene_number, style_reference="", seed=None):
    """Generate image and save to file"""
    
    consistency_keywords = "consistent character design, same art style, high quality, detailed, 4k"
    enhanced_prompt = f"{prompt}, {consistency_keywords}"
    encoded_prompt = urllib.parse.quote(enhanced_prompt)
    
    if seed:
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=576&seed={seed}&nologo=true"
    else:
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=576&nologo=true"
    
    image_path = f"scene_{scene_number}.png"
    
    try:
        print(f"🎨 Generating Scene {scene_number}...")
        
        response = requests.get(image_url, timeout=120)
        
        if response.status_code == 200:
            image = Image.open(BytesIO(response.content))
            
            # Add scene label
            draw = ImageDraw.Draw(image)
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
            except:
                font = ImageFont.load_default()
            
            draw.rectangle([10, 10, 150, 55], fill=(0, 0, 0))
            draw.text((20, 15), f"Scene {scene_number}", fill=(255, 255, 255), font=font)
            
            image.save(image_path)
            
            # Verify save
            if os.path.exists(image_path):
                print(f"✅ Scene {scene_number} saved: {image_path} ({os.path.getsize(image_path)} bytes)")
                files.add_image(scene_number, os.path.abspath(image_path))
                return os.path.abspath(image_path)
            else:
                print(f"⚠️ Failed to save image for scene {scene_number}")
                return create_placeholder(scene_number, prompt)
        else:
            print(f"⚠️ API error {response.status_code}")
            return create_placeholder(scene_number, prompt)
            
    except Exception as e:
        print(f"Error: {e}")
        return create_placeholder(scene_number, prompt)


def create_placeholder(scene_number, text=""):
    """Create placeholder image"""
    
    img = Image.new('RGB', (1024, 576), color=(40, 40, 60))
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except:
        font = ImageFont.load_default()
        small_font = font
    
    draw.text((50, 50), f"Scene {scene_number}", fill=(255, 255, 255), font=font)
    
    # Add wrapped text
    if text:
        words = text.split()[:25]
        lines = []
        current = []
        for word in words:
            current.append(word)
            if len(' '.join(current)) > 50:
                lines.append(' '.join(current[:-1]))
                current = [word]
        if current:
            lines.append(' '.join(current))
        
        y = 130
        for line in lines[:5]:
            draw.text((50, y), line, fill=(180, 180, 200), font=small_font)
            y += 30
    
    image_path = f"scene_{scene_number}.png"
    img.save(image_path)
    
    files.add_image(scene_number, os.path.abspath(image_path))
    print(f"✅ Placeholder for Scene {scene_number} saved: {image_path}")
    
    return os.path.abspath(image_path)


# =============================================================================
# TEXT-TO-SPEECH
# =============================================================================

async def tts_async(text, output_file, voice):
    """Async TTS generation"""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)


def generate_audio(text, scene_number, voice="en-US-AriaNeural"):
    """Generate narration audio"""
    
    audio_path = f"narration_{scene_number}.mp3"
    
    try:
        print(f"🎤 Generating narration for Scene {scene_number}...")
        
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(tts_async(text, audio_path, voice))
        loop.close()
        
        # Verify
        if os.path.exists(audio_path):
            size = os.path.getsize(audio_path)
            print(f"✅ Narration {scene_number} saved: {audio_path} ({size} bytes)")
            files.add_audio(scene_number, os.path.abspath(audio_path))
            return os.path.abspath(audio_path)
        else:
            print(f"⚠️ Audio file not created for scene {scene_number}")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None


# =============================================================================
# VIDEO CREATOR - COMPLETELY REWRITTEN
# =============================================================================

def create_simple_image(text_lines, filename, bg_color=(20, 20, 35), text_color=(255, 255, 255)):
    """Create a simple image with text"""
    
    img = Image.new('RGB', (1024, 576), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    try:
        large_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except:
        large_font = ImageFont.load_default()
        small_font = large_font
    
    y_start = 200
    for i, (text, is_large) in enumerate(text_lines):
        font = large_font if is_large else small_font
        
        # Center text
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            x = (1024 - text_width) // 2
        except:
            x = 100
        
        color = text_color if is_large else (150, 150, 180)
        draw.text((x, y_start + i * 60), text, fill=color, font=font)
    
    img.save(filename)
    return filename


def make_video_simple(story_data, num_scenes):
    """
    Create video using a SIMPLE and RELIABLE method
    """
    
    print("\n" + "=" * 70)
    print("🎬 CREATING VIDEO - SIMPLE METHOD")
    print("=" * 70)
    
    output_path = "final_storyboard.mp4"
    all_clips = []
    
    # ===========================================
    # STEP 1: CREATE TITLE CARD
    # ===========================================
    print("\n📌 Creating title card...")
    
    title = story_data.get("title", "My Story")[:40]
    title_img = "title_card.png"
    create_simple_image([
        (title, True),
        ("AI Generated Storyboard", False)
    ], title_img)
    
    try:
        title_clip = ImageClip(title_img).set_duration(3)
        all_clips.append(title_clip)
        print(f"   ✅ Title card added (3s)")
    except Exception as e:
        print(f"   ❌ Title card error: {e}")
    
    # ===========================================
    # STEP 2: ADD EACH SCENE
    # ===========================================
    print(f"\n📌 Adding {num_scenes} scenes...")
    
    for scene_num in range(1, num_scenes + 1):
        print(f"\n   --- Scene {scene_num} ---")
        
        # Get file paths
        image_path = files.get_image(scene_num)
        audio_path = files.get_audio(scene_num)
        
        print(f"   Image path: {image_path}")
        print(f"   Audio path: {audio_path}")
        
        # Check if image exists
        if not image_path or not os.path.exists(image_path):
            print(f"   ⚠️ Image not found, skipping scene {scene_num}")
            continue
        
        try:
            # Create image clip
            print(f"   Creating image clip...")
            img_clip = ImageClip(image_path)
            
            # Determine duration
            duration = 5.0  # Default duration
            audio_clip = None
            
            if audio_path and os.path.exists(audio_path):
                try:
                    print(f"   Loading audio...")
                    audio_clip = AudioFileClip(audio_path)
                    duration = audio_clip.duration + 1.0
                    print(f"   Audio duration: {audio_clip.duration:.2f}s, clip duration: {duration:.2f}s")
                except Exception as e:
                    print(f"   ⚠️ Audio load error: {e}")
                    audio_clip = None
                    duration = 5.0
            else:
                print(f"   No audio, using default {duration}s duration")
            
            # Set duration
            img_clip = img_clip.set_duration(duration)
            
            # Attach audio if available
            if audio_clip is not None:
                try:
                    img_clip = img_clip.set_audio(audio_clip)
                    print(f"   ✅ Audio attached")
                except Exception as e:
                    print(f"   ⚠️ Could not attach audio: {e}")
            
            # Add to list
            all_clips.append(img_clip)
            print(f"   ✅ Scene {scene_num} added ({duration:.2f}s)")
            
        except Exception as e:
            print(f"   ❌ Error processing scene {scene_num}: {e}")
            import traceback
            traceback.print_exc()
    
    # ===========================================
    # STEP 3: CREATE END CARD
    # ===========================================
    print("\n📌 Creating end card...")
    
    end_img = "end_card.png"
    create_simple_image([
        ("The End", True),
        ("Created with AI Storyboard Generator", False)
    ], end_img)
    
    try:
        end_clip = ImageClip(end_img).set_duration(3)
        all_clips.append(end_clip)
        print(f"   ✅ End card added (3s)")
    except Exception as e:
        print(f"   ❌ End card error: {e}")
    
    # ===========================================
    # STEP 4: COMBINE AND EXPORT
    # ===========================================
    print(f"\n📌 Combining {len(all_clips)} clips...")
    
    if len(all_clips) < 2:
        print("   ❌ Not enough clips!")
        return None
    
    try:
        # Print clip info
        print("\n   Clips to combine:")
        total_duration = 0
        for i, clip in enumerate(all_clips):
            print(f"      {i+1}. Duration: {clip.duration:.2f}s, Has audio: {clip.audio is not None}")
            total_duration += clip.duration
        print(f"   Total duration: {total_duration:.2f}s")
        
        # Concatenate
        print("\n   Concatenating...")
        final = concatenate_videoclips(all_clips, method="compose")
        
        # Export
        print(f"   Exporting to {output_path}...")
        print("   This may take 1-2 minutes...")
        
        final.write_videofile(
            output_path,
            fps=24,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp_audio.m4a',
            remove_temp=True,
            verbose=False,
            logger=None
        )
        
        # Cleanup
        print("   Cleaning up clips...")
        for clip in all_clips:
            try:
                clip.close()
            except:
                pass
        try:
            final.close()
        except:
            pass
        
        # Verify output
        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"\n✅ VIDEO CREATED SUCCESSFULLY!")
            print(f"   File: {output_path}")
            print(f"   Size: {size_mb:.2f} MB")
            print(f"   Duration: {total_duration:.2f}s")
            return os.path.abspath(output_path)
        else:
            print("   ❌ Output file not found!")
            return None
            
    except Exception as e:
        print(f"   ❌ Error creating video: {e}")
        import traceback
        traceback.print_exc()
        return None


# =============================================================================
# MAIN GENERATOR
# =============================================================================

def generate_storyboard(story_idea, num_scenes=4, voice="en-US-AriaNeural"):
    """Main generation function"""
    
    print("\n" + "=" * 70)
    print("🎬 AI STORYBOARD GENERATOR")
    print("=" * 70)
    print(f"Story: {story_idea[:50]}...")
    print(f"Scenes: {num_scenes}")
    print(f"Voice: {voice}")
    
    # Reset file tracker
    files.reset()
    
    results = {
        "status": "processing",
        "story": None,
        "images": [],
        "audio": [],
        "video": None
    }
    
    # ===========================================
    # STEP 1: GENERATE STORY
    # ===========================================
    print("\n" + "-" * 50)
    print("📝 STEP 1: Generating story...")
    print("-" * 50)
    
    story_data = generate_consistent_story(story_idea, num_scenes)
    
    if not story_data:
        results["status"] = "error"
        results["error"] = "Failed to generate story"
        return results
    
    results["story"] = story_data
    
    actual_scenes = story_data.get("scenes", [])
    print(f"✅ Story: '{story_data.get('title', 'Untitled')}'")
    print(f"✅ Generated {len(actual_scenes)} scenes")
    
    # Get style info
    visual_bible = story_data.get("visual_bible", {})
    style_ref = f"{visual_bible.get('art_style', '')}, {visual_bible.get('color_palette', '')}"
    base_seed = hash(story_idea) % 100000
    
    # ===========================================
    # STEP 2: GENERATE IMAGES
    # ===========================================
    print("\n" + "-" * 50)
    print(f"🎨 STEP 2: Generating {len(actual_scenes)} images...")
    print("-" * 50)
    
    for i, scene in enumerate(actual_scenes):
        scene_num = i + 1
        prompt = scene.get("visual_prompt", f"Scene {scene_num}")
        seed = base_seed + i
        
        image_path = generate_image(prompt, scene_num, style_ref, seed)
        results["images"].append(image_path)
        
        time.sleep(2)  # Rate limiting
    
    # ===========================================
    # STEP 3: GENERATE AUDIO
    # ===========================================
    print("\n" + "-" * 50)
    print(f"🎤 STEP 3: Generating {len(actual_scenes)} narrations...")
    print("-" * 50)
    
    for i, scene in enumerate(actual_scenes):
        scene_num = i + 1
        narration = scene.get("narration", "")
        
        if narration:
            audio_path = generate_audio(narration, scene_num, voice)
            results["audio"].append(audio_path)
        else:
            print(f"⚠️ No narration for scene {scene_num}")
            results["audio"].append(None)
    
    # ===========================================
    # STEP 4: SHOW FILE SUMMARY
    # ===========================================
    files.summary()
    
    # ===========================================
    # STEP 5: CREATE VIDEO
    # ===========================================
    print("\n" + "-" * 50)
    print("🎬 STEP 4: Creating video...")
    print("-" * 50)
    
    video_path = make_video_simple(story_data, len(actual_scenes))
    results["video"] = video_path
    
    if video_path:
        results["status"] = "completed"
    else:
        results["status"] = "partial"
        results["error"] = "Images generated but video creation failed"
    
    # ===========================================
    # FINAL SUMMARY
    # ===========================================
    print("\n" + "=" * 70)
    print("🏁 COMPLETE!")
    print("=" * 70)
    print(f"Status: {results['status']}")
    print(f"Images: {len([i for i in results['images'] if i])}")
    print(f"Audio: {len([a for a in results['audio'] if a])}")
    print(f"Video: {results['video']}")
    
    return results


# =============================================================================
# GRADIO INTERFACE
# =============================================================================

def process_request(story_idea, num_scenes, voice_choice):
    """Process Gradio request"""
    
    if not story_idea or len(story_idea.strip()) < 10:
        return "❌ Please enter a longer story idea", [], None, "Error: Too short"
    
    voice_map = {
        "Female (US) - Aria": "en-US-AriaNeural",
        "Male (US) - Guy": "en-US-GuyNeural",
        "Female (UK) - Sonia": "en-GB-SoniaNeural",
        "Female (Australian) - Natasha": "en-AU-NatashaNeural",
        "Male (UK) - Ryan": "en-GB-RyanNeural"
    }
    
    voice = voice_map.get(voice_choice, "en-US-AriaNeural")
    
    # Generate
    results = generate_storyboard(story_idea, int(num_scenes), voice)
    
    if results["status"] in ["completed", "partial"]:
        story_data = results["story"]
        
        # Format text output
        text = f"# 📖 {story_data.get('title', 'My Story')}\n\n"
        
        vb = story_data.get("visual_bible", {})
        if vb:
            text += "## 🎨 Visual Style\n"
            text += f"**Art Style:** {vb.get('art_style', 'N/A')}\n\n"
            text += f"**Colors:** {vb.get('color_palette', 'N/A')}\n\n"
            text += f"**Character:** {vb.get('main_character', 'N/A')}\n\n"
            text += "---\n\n"
        
        text += "## 🎬 Scenes\n\n"
        for scene in story_data.get("scenes", []):
            text += f"### Scene {scene.get('scene_number', '?')}\n"
            text += f"**Description:** {scene.get('description', '')}\n\n"
            text += f"**Narration:** _{scene.get('narration', '')}_\n\n"
            text += "---\n\n"
        
        # Load images
        images = []
        for img_path in results["images"]:
            if img_path and os.path.exists(img_path):
                try:
                    images.append(Image.open(img_path))
                except:
                    pass
        
        status = "✅ Complete!" if results["status"] == "completed" else "⚠️ Partial (check video)"
        
        return text, images, results["video"], status
    else:
        return "❌ Generation failed", [], None, f"Error: {results.get('error', 'Unknown')}"


# =============================================================================
# GRADIO UI
# =============================================================================

with gr.Blocks(
    title="AI Storyboard Generator",
    theme=gr.themes.Soft()
) as demo:
    
    gr.Markdown("""
    # 🎬 AI Storyboard Generator
    ### Turn your ideas into visual stories!
    
    **Features:** AI Story Writing • Consistent Characters • Voice Narration • Video Export
    
    ---
    """)
    
    with gr.Row():
        with gr.Column(scale=1):
            story_input = gr.Textbox(
                label="📝 Your Story Idea",
                placeholder="A robot discovers a magical garden...",
                lines=5
            )
            
            num_scenes = gr.Slider(2, 8, value=4, step=1, label="🎞️ Scenes")
            
            voice_choice = gr.Dropdown(
                ["Female (US) - Aria", "Male (US) - Guy", "Female (UK) - Sonia", 
                 "Female (Australian) - Natasha", "Male (UK) - Ryan"],
                value="Female (US) - Aria",
                label="🎤 Voice"
            )
            
            btn = gr.Button("🎬 Generate", variant="primary", size="lg")
            status = gr.Textbox(label="Status", interactive=False)
            
            gr.Markdown("**⏱️ ~30-45 sec/scene**")
        
        with gr.Column(scale=2):
            with gr.Tabs():
                with gr.TabItem("📖 Script"):
                    script_out = gr.Markdown()
                with gr.TabItem("🖼️ Images"):
                    gallery = gr.Gallery(columns=2, height=450)
                with gr.TabItem("🎬 Video"):
                    video_out = gr.Video(height=400)
    
    gr.Markdown("### 📚 Examples")
    gr.Examples(
        [
            ["A small robot wakes up in an abandoned factory and finds a garden where nature and machines live together", 4, "Female (US) - Aria"],
            ["A young witch's first day at magic school goes wrong when her spells backfire", 4, "Female (UK) - Sonia"],
            ["An old fisherman tells his grandson about meeting a friendly sea dragon", 3, "Male (US) - Guy"],
        ],
        [story_input, num_scenes, voice_choice]
    )
    
    btn.click(process_request, [story_input, num_scenes, voice_choice], [script_out, gallery, video_out, status])

print("✅ Ready!")

if __name__ == "__main__":
    demo.launch()
