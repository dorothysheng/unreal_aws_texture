# import importlib, aws_texture_tool as t
# importlib.reload(t)
# t.unregister_menu(); t.register_menu()

# UE5.6: AWS Texture Tool - SIMPLIFIED VERSION
# Menu: Edit ▸ Generate Texture (AWS)

import os
import re
import json
import base64
import tempfile
import unreal

# -------- CONFIG --------
AWS_REGION   = "us-west-2"
MODEL_ID     = "amazon.titan-image-generator-v1"
DEFAULT_SIZE = (512, 512)
DEST_PATH    = "/Game/Generated"
# ------------------------

def _sanitize_name(s: str, prefix="T_", maxlen=48):
    s = re.sub(r"[^0-9A-Za-z]+", "_", s).strip("_")
    return (prefix + s)[:maxlen] or (prefix + "Generated")

def _bedrock_text_to_image(prompt: str, model_id: str, region: str, size):
    """Call AWS Bedrock, return PNG bytes."""
    try:
        import boto3
    except ImportError:
        unreal.log_error("boto3 not found. Install it into Unreal's Python.")
        raise

    w, h = size
    client = boto3.client("bedrock-runtime", region_name=region)

    if model_id.startswith("amazon.titan"):
        body = json.dumps({
            "taskType": "TEXT_IMAGE",
            "textToImageParams": {"text": prompt},
            "imageGenerationConfig": {
                "numberOfImages": 1, "height": h, "width": w,
                "cfgScale": 8.0, "seed": 0
            }
        })
        resp = client.invoke_model(modelId=model_id, body=body)
        data = json.loads(resp["body"].read())
        b64 = data["images"][0]
    else:
        body = json.dumps({
            "text_prompts": [{"text": prompt}],
            "cfg_scale": 7, "steps": 30, "samples": 1,
            "width": w, "height": h
        })
        resp = client.invoke_model(modelId=model_id, body=body)
        data = json.loads(resp["body"].read())
        b64 = data["artifacts"][0]["base64"]

    return base64.b64decode(b64)

def _import_png_as_texture(png_bytes, asset_name: str, dest_path: str):
    """Import PNG bytes as Texture2D."""
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    try:
        tf.write(png_bytes); tf.close()

        task = unreal.AssetImportTask()
        task.filename = tf.name
        task.destination_path = dest_path
        task.destination_name = asset_name
        task.automated = True
        task.replace_existing = True
        task.save = True

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        if task.imported_object_paths:
            return unreal.load_asset(task.imported_object_paths[0])
        return None
    finally:
        try: os.remove(tf.name)
        except Exception: pass

def _parse_size(text: str):
    if not text or not text.strip():
        return DEFAULT_SIZE
    m = re.match(r"^\s*(\d+)\s*[x,]\s*(\d+)\s*$", text.strip(), re.I)
    if not m:
        raise ValueError("Size must look like 512x512 or 1024,1024")
    return int(m.group(1)), int(m.group(2))

def _focus_in_browser(asset: unreal.Object):
    """Focus Content Browser to asset."""
    obj_path = asset.get_path_name()
    if " " in obj_path:
        obj_path = obj_path.split(" ", 1)[1]
    try:
        unreal.EditorAssetLibrary.sync_browser_to_objects([obj_path])
    except Exception as e:
        unreal.log_warning(f"Could not focus asset: {e}")

# ========== INPUT ==========

def get_user_input():
    """Get user input via tkinter"""
    try:
        import tkinter as tk
        from tkinter import simpledialog
        
        root = tk.Tk()
        root.withdraw()
        root.lift()
        root.attributes('-topmost', True)
        
        prompt = simpledialog.askstring(
            "AWS Texture Generator",
            "Enter text prompt:",
            initialvalue="blue neon 'HELLO' logo on dark background"
        )
        
        if not prompt or not prompt.strip():
            root.destroy()
            return None, None, None
        
        size_str = simpledialog.askstring(
            "Image Size",
            "Enter size (e.g. 512x512):",
            initialvalue="512x512"
        )
        
        if not size_str or not size_str.strip():
            size_str = "512x512"
        
        dest = simpledialog.askstring(
            "Destination",
            "Enter destination path:",
            initialvalue=DEST_PATH
        )
        
        if not dest or not dest.strip():
            dest = DEST_PATH
        
        root.destroy()
        size = _parse_size(size_str)
        return prompt, size, dest
        
    except Exception as e:
        unreal.log_error(f"Input failed: {e}")
        return None, None, None

# ========== MAIN FUNCTIONS ==========

def generate_texture_from_text(prompt: str,
                               model_id: str = MODEL_ID,
                               region: str = AWS_REGION,
                               size = DEFAULT_SIZE,
                               dest_path: str = DEST_PATH):
    """Generate texture from text"""
    with unreal.ScopedSlowTask(3, "Generating texture from AWS Bedrock...") as slow:
        slow.make_dialog(True)
        slow.enter_progress_frame(1, "Calling AWS Bedrock...")
        png_bytes = _bedrock_text_to_image(prompt, model_id, region, size)

        slow.enter_progress_frame(1, "Importing texture...")
        asset_name = _sanitize_name(prompt)
        tex = _import_png_as_texture(png_bytes, asset_name, dest_path)

        slow.enter_progress_frame(1, "Done")
        if tex:
            unreal.log(f"Created: {tex.get_path_name()}")
        else:
            unreal.log_error("Import failed")
        return tex

def run_texture_generator():
    """Main function"""
    try:
        inputs = get_user_input()
        if not inputs or not inputs[0]:
            unreal.log("Cancelled")
            return None
        
        prompt, size, dest = inputs
        unreal.log(f"Generating: '{prompt}' {size[0]}x{size[1]} -> {dest}")
        
        texture = generate_texture_from_text(prompt, MODEL_ID, AWS_REGION, size, dest)
        
        if texture:
            _focus_in_browser(texture)
            unreal.log(f"Success: {texture.get_name()}")
            return texture
        else:
            unreal.log_error("Failed")
            return None
            
    except Exception as e:
        unreal.log_error(f"Error: {e}")
        return None

def quick_generate(prompt=None, size_str="512x512", dest=None):
    """Quick generate function
    
    Examples:
    quick_generate("cyberpunk robot")
    quick_generate("dragon", "1024x1024", "/Game/Dragons")
    """
    try:
        if not prompt:
            prompt = "blue neon logo"
        if not dest:
            dest = DEST_PATH
        
        size = _parse_size(size_str)
        texture = generate_texture_from_text(prompt, MODEL_ID, AWS_REGION, size, dest)
        
        if texture:
            _focus_in_browser(texture)
            unreal.log(f"Generated: {texture.get_name()}")
            return texture
        else:
            unreal.log_error("Quick generation failed")
            return None
            
    except Exception as e:
        unreal.log_error(f"Error: {e}")
        return None

# ========== MENU ==========

_ENTRY_NAME = "AWS_GenerateTexture"

@unreal.uclass()
class AWSGenTextureEntry(unreal.ToolMenuEntryScript):
    @unreal.ufunction(override=True)
    def execute(self, context: unreal.ToolMenuContext):
        run_texture_generator()

def register_menu():
    """Register menu"""
    menus = unreal.ToolMenus.get()
    edit_menu = menus.find_menu("LevelEditor.MainMenu.Edit")
    
    if edit_menu:
        try:
            menus.remove_menu_entry(edit_menu.menu_name, "EditMain", _ENTRY_NAME)
        except:
            pass
        
        script_obj = AWSGenTextureEntry()
        script_obj.init_entry(
            owner_name=edit_menu.menu_name,
            menu=edit_menu.menu_name,
            section="EditMain",
            name=_ENTRY_NAME,
            label="Generate Texture (AWS)",
            tool_tip="Generate Texture2D from text using AWS Bedrock"
        )
        script_obj.register_menu_entry()
        unreal.log("Registered: Edit > Generate Texture (AWS)")
    
    menus.refresh_all_widgets()

def unregister_menu():
    """Unregister menu"""
    menus = unreal.ToolMenus.get()
    try:
        menus.remove_menu_entry("LevelEditor.MainMenu.Edit", "EditMain", _ENTRY_NAME)
    except:
        pass
    menus.refresh_all_widgets()
    unreal.log("Unregistered menu")

# Auto-register
if __name__ == "__main__":
    register_menu()

# Usage:
# - Menu: Edit > Generate Texture (AWS)
# - Console: run_texture_generator()
# - Quick: quick_generate("prompt")