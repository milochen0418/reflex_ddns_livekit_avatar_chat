import reflex as rx
from dotenv import load_dotenv

load_dotenv()

config = rx.Config(
    app_name="reflex_ddns_livekit_avatar_chat",
    plugins=[rx.plugins.TailwindV3Plugin()],
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
)
