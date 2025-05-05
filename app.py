import streamlit as st
import google.generativeai as genai
import os
import json
import re # Import regex for parsing
# --- API Key Configuration ---
api_key = None
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    st.session_state.api_configured = True
except KeyError:
    # If not in secrets, try environment variable
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            genai.configure(api_key=api_key)
            st.session_state.api_configured = True
        except Exception as e:
            st.error(f"Error configuring Gemini API with environment variable key: {e}")
            st.session_state.api_configured = False
    else:
        # If no key found in either place
        st.session_state.api_configured = False
except Exception as e:
    # Catch potential configuration errors from secrets
    st.error(f"Error configuring Gemini API with secrets key: {e}")
    st.session_state.api_configured = False

if not st.session_state.get("api_configured", False):
     st.error("Gemini API Key not found or configuration failed. Please set it in Streamlit secrets or as an environment variable (GEMINI_API_KEY).")
     # We don't stop here immediately, allow the UI to render,
     # but the button click will check this flag later.


# --- Model Configuration ---
MODEL_NAME = "models/gemini-2.5-flash-preview-04-17" # Using the specified model
generation_config = {
    "temperature": 0.7,
    "top_p": 1.0,
    "top_k": 32,
    "max_output_tokens": 2048, # Increased tokens for explanation
    "response_mime_type": "application/json", # Instruct the model to output JSON

}
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

# Initialize model only if API is configured and model not already in state
if st.session_state.get("api_configured", False) and 'gemini_model' not in st.session_state:
    try:
        st.session_state.gemini_model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            generation_config=generation_config,
            safety_settings=safety_settings
        )
    except Exception as e:
        st.error(f"Failed to initialize the AI model: {e}")
        st.stop() # Stop if model initialization fails

# --- Streamlit App ---

st.set_page_config(page_title="RightOrRude", layout="centered")
st.title("⚖️ RightOrRude")
st.caption("Let AI help you judge your situation, inspired by AITA.")

scenario = st.text_area("Describe your scenario:", height=200, placeholder="Tell me what happened...")

if st.button("Judge Me!"):
    # Check configuration status *before* attempting to use the model
    if not st.session_state.get("api_configured", False):
         st.error("API Key not configured or model not initialized. Cannot proceed.")
    elif 'gemini_model' not in st.session_state:
         st.error("AI Model not initialized. Cannot proceed.")
    elif not scenario:
        st.warning("Please describe your scenario first.")
    else:
        model = st.session_state.gemini_model # Get model from session state
        prompt = f"""
        Analyze the following scenario based on the AITA (Am I The Asshole?) framework.
        Respond ONLY with a valid JSON object containing the following keys:
        - "verdict": A string, one of "NTA", "YTA", "ESH", "NAH", "INFO".
        - "score": An integer between 0 and 100 (0=NTA, 100=YTA).
        - "explanation": A string briefly explaining the reasoning for the verdict and score.

        Ensure the output is nothing but the JSON object itself.

        Scenario:
        {scenario}
        """
        try:
            with st.spinner("Deliberating..."):
                response = model.generate_content(prompt)
                response_text = response.text.strip()

            # --- Parse the JSON response ---
            verdict = "Error"
            score = 50 # Default score if parsing fails
            explanation = "Could not parse the model's response."
            data = None
            valid_verdicts = ["NTA", "YTA", "ESH", "NAH", "INFO"]

            max_attempts = 3
            attempt = 0
            while attempt < max_attempts:
                try:
                    data = json.loads(response_text)
                    # Validate structure and values
                    if isinstance(data, dict) and \
                       'verdict' in data and isinstance(data['verdict'], str) and data['verdict'] in valid_verdicts and \
                       'score' in data and isinstance(data['score'], int) and \
                       'explanation' in data and isinstance(data['explanation'], str):

                        verdict = data['verdict']
                        # Clamp score just in case model returns out-of-range value
                        score = max(0, min(100, data['score']))
                        explanation = data['explanation']
                        break
                    else:
                        st.warning(f"Parsed JSON does not match expected format. Data: {data}")
                        explanation = f"Parsed JSON does not match expected format.\nRaw Response:\n```\n{response_text}\n```"
                        break
                except json.JSONDecodeError as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        st.warning(f"Failed to decode JSON response from model after {max_attempts} attempts: {e}")
                        explanation = f"Model did not return valid JSON.\nRaw Response:\n```\n{response_text}\n```"

            # --- Display results ---
            st.subheader("Verdict:")
            if verdict in valid_verdicts:
                 st.markdown(f"## {verdict}")
                 if verdict == "NTA":
                     st.success("You are likely not the asshole.")
                 elif verdict == "YTA":
                     st.error("You might be the asshole.")
                 elif verdict == "ESH":
                     st.warning("It seems everyone involved shares some blame.")
                 elif verdict == "NAH":
                     st.info("No assholes here, just a complex situation.")
                 elif verdict == "INFO":
                     st.info("More information is needed to make a clear judgment.")

                 # Display Score Bar
                 st.subheader("AITA Score:")
                 # Ensure score is treated as float for progress bar
                 st.progress(float(score) / 100.0)
                 st.caption(f"{score}% likelihood of being the Asshole")

                 # Display Explanation
                 st.subheader("Explanation:")
                 st.markdown(explanation) # Display the parsed or error explanation

            else: # Handle cases where verdict remains "Error" after parsing attempt
                 st.error("Failed to get a valid verdict from the model.")
                 st.subheader("Explanation:")
                 st.markdown(explanation) # Show parsing error/raw response


        except Exception as e:
            st.error(f"An error occurred while contacting the AI model: {e}")
            st.exception(e) # Show traceback for debugging

st.markdown("---")
st.markdown("Note, don't use this with your partner - it will likely piss them off.")
