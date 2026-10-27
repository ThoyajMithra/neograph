import os
from engine.embedding.encoder import RemoteEncoder  # Replace with the actual module name where your class is located

# # 1. Set environment variables (or set them beforehand in the terminal)
# os.environ["CLOUDFLARE_ACCOUNT_ID"] = "cba9277db7284c22c54ae042e190c2ac"
# # os.environ["CLOUDFLARE_API_TOKEN"] = "your_api_token_here"
# os.environ["EMBEDDING_MODEL_NAME"] = "@cf/baai/bge-small-en-v1.5" # You can also change to another model

# 2. Instantiate the encoder
encoder = RemoteEncoder(model_name=os.getenv("EMBEDDING_MODEL_NAME"))

# 3. Test a single string
print("--- Testing single string ---")
single_text = "This is a test sentence."
single_result = encoder.encode(single_text)
print(f"Input: {single_text}")
print(f"Output type: {type(single_result)}")
print(f"Output length: {len(single_result)}")
print(f"Vector dimensions: {len(single_result[0])}")
print(f"First 3 values of the vector: {single_result[0][:3]}")

# 4. Test a list of strings
print("\n--- Testing string list ---")
multi_texts = ["First sentence.", "Second sentence."]
multi_result = encoder.encode(multi_texts)
print(f"Input: {multi_texts}")
print(f"Output type: {type(multi_result)}")
print(f"Output length: {len(multi_result)}")
print(f"Vector dimensions: {len(multi_result[0])}")

# 5. Close the client (if your class implements the close method)
# encoder.close()