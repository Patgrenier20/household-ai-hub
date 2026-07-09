import streamlit as st
from ollama import Client
import pypdf
import json
import os
from datetime import datetime

# 1. PAGE CONFIG MUST BE FIRST!
st.set_page_config(
    page_title="Household AI Hub", 
    page_icon="🤖", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- NEW: CHAT HISTORY HELPER FUNCTIONS ---
CHAT_FILE = "household_chats.json"

def load_all_chats():
    """Loads all saved chats from the JSON file."""
    if os.path.exists(CHAT_FILE):
        with open(CHAT_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_current_chat():
    """Saves the current session state to the JSON file."""
    if not st.session_state.messages: 
        return
        
    chats = load_all_chats()
    
    # Create a title based on the time and the first message
    first_msg = next((m["content"] for m in st.session_state.messages if m["role"] == "user"), "New Chat")
    clean_title = first_msg[:25].replace('\n', ' ') + "..."
    timestamp = datetime.now().strftime('%Y-%m-%d %I:%M %p')
    chat_id = f"{timestamp} | {clean_title}"
    
    chats[chat_id] = st.session_state.messages
    
    with open(CHAT_FILE, "w") as f:
        json.dump(chats, f)
        
    return chat_id

# 2. Initialize Client
ollama_client = Client(host='http://127.0.0.1:11434')

# 3. Fetch available models and check their capabilities
model_options = {}
try:
    models_response = ollama_client.list()
    models_list = getattr(models_response, 'models', models_response.get('models', []))
    
    for m in models_list:
        model_name = getattr(m, 'model', m.get('name'))
        try:
            model_info = ollama_client.show(model_name)
            model_info_str = str(model_info).lower()
            
            if "vision" in model_info_str or "clip" in model_info_str:
                display_name = f"👁️ {model_name} (Vision)"
            else:
                display_name = f"📝 {model_name} (Text)"
                
            model_options[display_name] = model_name
        except Exception:
            model_options[f"❓ {model_name}"] = model_name
except Exception as e:
    st.error(f"Could not fetch models from Ollama: {e}")
    model_options = {"hf.co/King3Djbl/mythos-9b-unhinged:Q4_K_M": "hf.co/King3Djbl/mythos-9b-unhinged:Q4_K_M"}

# 4. Inject Custom CSS
st.markdown("""
<style>
    h1 { color: #4CAF50; text-align: center; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .stChatMessage { font-size: 1.15rem; }
</style>
""", unsafe_allow_html=True)

# 5. Sidebar Configuration
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/8649/8649603.png", width=100)
    st.title("Control Panel")
    
    # Model Dropdown
    selected_display = st.selectbox("🧠 Choose a Model", list(model_options.keys()))
    selected_model = model_options[selected_display] 
    st.divider()
    
    # --- NEW: CHAT HISTORY UI ---
    st.write("💾 **Save & Load Chats**")
    
    # Save button
    if st.button("📥 Save Current Chat", use_container_width=True):
        if st.session_state.messages:
            save_current_chat()
            st.success("Chat saved securely!")
        else:
            st.warning("Nothing to save yet.")
            
    # Load dropdown
    saved_chats = load_all_chats()
    if saved_chats:
        chat_to_load = st.selectbox("📂 Load a Past Chat", ["-- Select a Chat --"] + list(saved_chats.keys()))
        if chat_to_load != "-- Select a Chat --":
            if st.button("Load Selected Chat", use_container_width=True):
                st.session_state.messages = saved_chats[chat_to_load]
                st.rerun()
                
    st.divider()
    
    # File Uploader
    st.write("📎 **Attach Context**")
    uploaded_file = st.file_uploader("Upload a PDF or Image", type=["pdf", "png", "jpg", "jpeg"])
    st.caption("⚠️ *Images require a vision model (like llava). PDFs work with any model.*")
    st.divider()
    
    # Clear Chat Button
    if st.button("🗑️ Start New Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# 6. Main UI Header
st.title("🏠 The Household AI Hub")
st.markdown("<p style='text-align: center; color: gray;'>Ask me anything, I'm running right here on our home network!</p>", unsafe_allow_html=True)
st.divider() 

# 7. Initialize and Display Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    avatar = "👤" if message["role"] == "user" else "🤖"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message.get("display", message["content"]))

# 8. React to User Input
if prompt := st.chat_input("What's on your mind?"):
    
    display_text = prompt
    full_prompt_content = prompt
    image_bytes_list = []
    
    if uploaded_file:
        if uploaded_file.name.lower().endswith(".pdf"):
            try:
                pdf_reader = pypdf.PdfReader(uploaded_file)
                pdf_text = "".join([page.extract_text() + "\n" for page in pdf_reader.pages])
                full_prompt_content = f"Here is the content of an uploaded PDF document:\n\n{pdf_text}\n\n---\nUser Question: {prompt}"
                display_text = f"{prompt}\n\n*(📎 Attached PDF: {uploaded_file.name})*"
            except Exception as e:
                st.error(f"Could not read PDF: {e}")
        else:
            image_bytes_list.append(uploaded_file.getvalue())
            display_text = f"{prompt}\n\n*(🖼️ Attached Image: {uploaded_file.name})*"

    with st.chat_message("user", avatar="👤"):
        st.markdown(display_text)
    
    st.session_state.messages.append({
        "role": "user", 
        "content": full_prompt_content,
        "display": display_text,
        "images": image_bytes_list
    })

    with st.chat_message("assistant", avatar="🤖"):
        def generate_response():
            api_messages = []
            for msg in st.session_state.messages:
                api_msg = {"role": msg["role"], "content": msg["content"]}
                if msg.get("images"):
                    api_msg["images"] = msg["images"]
                api_messages.append(api_msg)

            stream = ollama_client.chat(
                model=selected_model,
                messages=api_messages,
                stream=True,
                options={"think": False} 
            )
            for chunk in stream:
                yield chunk['message']['content']
        
        try:
            response = st.write_stream(generate_response())
            st.session_state.messages.append({
                "role": "assistant", 
                "content": response,
                "display": response
            })
        except Exception as e:
            st.error(f"Error communicating with model: {e}. (Did you send an image to a text-only model?)")