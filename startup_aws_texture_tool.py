import unreal
try:
    import aws_texture_tool as t
    t.register_menu()
    unreal.log("AWS Texture tool registered.")
except Exception as e:
    unreal.log_error(f"Startup registration failed: {e}")