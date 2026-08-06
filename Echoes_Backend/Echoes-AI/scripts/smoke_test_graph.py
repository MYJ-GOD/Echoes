import asyncio
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.graph import agent_graph
from common.config import settings

async def main():
    print("--- Starting Smoke Test ---")
    print(f"Repo Dir: {settings.COSYVOICE_REPO_DIR}")
    print(f"Model Dir: {settings.ECHOES_MODELS_DIR}")

    # Mock input
    # We need a reference audio for zero-shot cloning
    # Let's look for one in the third_party dir to use as test
    ref_audio = os.path.join(settings.COSYVOICE_REPO_DIR, "asset", "zero_shot_prompt.wav")
    
    if not os.path.exists(ref_audio):
        print(f"Warning: Reference audio not found at {ref_audio}. Using SFT mode instead.")
        ref_audio = None
    else:
        print(f"Using reference audio: {ref_audio}")

    initial_state = {
        "messages": [],
        "input_text": "Hello, this is a test of the Echoes AI system.",
        "ref_audio_path": ref_audio,
        "ref_text": "希望你以后能够做的比我还好呦。", # Default prompt text for the asset wav
        "session_id": "test-session-001",
        "audio_chunks": []
    }

    print("--- Invoking Graph ---")
    try:
        # Run the graph
        final_state = await agent_graph.ainvoke(initial_state)
        
        print("--- Graph Execution Complete ---")
        print(f"LLM Response: {final_state['messages'][-1].content}")
        
        chunks = final_state.get("audio_chunks", [])
        print(f"Generated Audio Chunks: {len(chunks)}")
        
        if chunks:
            total_size = sum(len(c) for c in chunks)
            print(f"Total Audio Size: {total_size} bytes")
            
            # Save to file for verification
            output_file = "test_output.pcm"
            with open(output_file, "wb") as f:
                for chunk in chunks:
                    f.write(chunk)
            print(f"Saved audio to {output_file} (Raw PCM 16bit, 24kHz)")
            
    except Exception as e:
        print(f"Graph Execution Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
