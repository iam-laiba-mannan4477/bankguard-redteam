import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ["NEBIUS_API_KEY"],
)

ids = sorted(m.id for m in client.models.list())
print("Total models:", len(ids))
print("\n--- Nemotron / NVIDIA ---")
for i in ids:
    if "nemotron" in i.lower() or i.lower().startswith("nvidia"):
        print(i)
print("\n--- Guard / safety / shield ---")
hits = [i for i in ids if any(k in i.lower() for k in ("guard", "safety", "shield"))]
print("\n".join(hits) if hits else "(none found)")