import streamlit as st
import google.generativeai as genai
import os
import json
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

# Define Personas and their instructions
personas = {
    "Brittany": "Analyze this scenario from the perspective of a sassy GenZ chick. Your language should be informal, use some slang, and focus on modern social dynamics and 'vibes'. Be brutally honest but maybe with a hint of humor.",
    "Chad": "Analyze this scenario from the perspective of a 'based gym bro'. Your judgment should be direct, perhaps a bit blunt, and focus on personal accountability and strength. Use simple, straightforward language.",
    "Mom": "Analyze this scenario from the perspective of a wise and experienced parent. Focus on empathy, communication, and the long-term consequences of actions on relationships and personal growth. Offer compassionate but firm advice.",
    "Prof. Dr. Socrates": "Analyze this scenario from the perspective of a psychology professor. Focus on underlying motivations, cognitive biases, interpersonal dynamics, and potential psychological impacts. Use academic but accessible language.",
    "Mrs. Jackson": "Analyze this scenario from the perspective of a teacher. Focus on fairness, rules, consequences, and what could be learned from the situation. Provide guidance as if explaining a lesson."
}

# Function to parse model response
def parse_response(response_text, persona_name="Model"):
    verdict = "Error"
    score = 50
    explanation = f"Could not parse the response for {persona_name}."
    data = None
    valid_verdicts = ["NTA", "YTA", "ESH", "NAH", "INFO"]

    try:
        data = json.loads(response_text)
        if isinstance(data, dict) and \
           'verdict' in data and isinstance(data['verdict'], str) and data['verdict'] in valid_verdicts and \
           'score' in data and isinstance(data['score'], int) and \
           'explanation' in data and isinstance(data['explanation'], str):
            verdict = data['verdict']
            score = max(0, min(100, data['score']))
            explanation = data['explanation']
        else:
            explanation = f"Parsed JSON for {persona_name} does not match expected format.\nRaw Response:\n```\n{response_text}\n```"
    except json.JSONDecodeError as e:
        explanation = f"Failed to decode JSON response for {persona_name}: {e}\nRaw Response:\n```\n{response_text}\n```"
    return verdict, score, explanation

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
        persona_results = []
        with st.spinner("Getting opinions from the reviewers..."):
            for persona_name, persona_instruction in personas.items():
                persona_prompt = f"""
                Analyze the following scenario based on the AITA (Am I The Asshole?) framework.
                Adopt the persona of a '{persona_name}' with the following instructions: {persona_instruction}

                Respond ONLY with a valid JSON object containing the following keys:
                - "verdict": A string, one of "NTA", "YTA", "ESH", "NAH", "INFO".
                - "score": An integer between 0 and 100 (0=NTA, 100=YTA).
                - "explanation": A string explaining the reasoning for the verdict and score from your persona's viewpoint. Keep this explanation concise, ideally around two sentences. If the verdict is "YTA", the explanation should be significantly harsher and more direct in its criticism of the user's actions from your persona's viewpoint.

                Ensure the output is nothing but the JSON object itself.

                Scenario:
                {scenario}
                """
                try:
                    response = model.generate_content(persona_prompt)
                    response_text = response.text.strip()
                    verdict, score, explanation = parse_response(response_text, persona_name)
                    persona_results.append({
                        "name": persona_name,
                        "verdict": verdict,
                        "score": score,
                        "explanation": explanation
                    })
                except Exception as e:
                    st.error(f"Error generating response for {persona_name}: {e}")
                    persona_results.append({
                         "name": persona_name,
                         "verdict": "Error",
                         "score": 50,
                         "explanation": f"An error occurred: {e}"
                    })

        # --- Judge Model ---
        judge_prompt = f"""
        You are the final judge in an AITA (Am I The Asshole?) scenario.
        You have received the following scenario and several opinions from different reviewers.
        Your task is to synthesize these opinions, the original scenario, and provide a final, objective verdict, score, and explanation.
        Do not just average the results; provide a considered judgment based on the evidence and arguments presented by the reviewers.
        If reviewers disagree, analyze the points of disagreement and determine which perspective is more convincing or applicable.

        Original Scenario:
        {scenario}

        Reviewer Opinions:
        """
        for res in persona_results:
            judge_prompt += f"\n--- {res['name']} ---\n"
            judge_prompt += f"Verdict: {res['verdict']}\n"
            judge_prompt += f"Score: {res['score']}\n"
            judge_prompt += f"Explanation: {res['explanation']}\n"

        judge_prompt += """
        Based on the above, provide your final judgment.
        Respond ONLY with a valid JSON object containing the following keys:
        - "verdict": A string, one of "NTA", "YTA", "ESH", "NAH", "INFO".
        - "score": An integer between 0 and 100 (0=NTA, 100=YTA).
        - "explanation": A string explaining your final reasoning, referencing the reviewer opinions where relevant. Your explanation should be objective and comprehensive.

        Ensure the output is nothing but the JSON object itself.
        """
        final_verdict = "Error"
        final_score = 50
        final_explanation = "Could not get a final judgment."
        valid_verdicts = ["NTA", "YTA", "ESH", "NAH", "INFO"]


        with st.spinner("The judge is deliberating..."):
            try:
                judge_response = model.generate_content(judge_prompt)
                judge_response_text = judge_response.text.strip()
                final_verdict, final_score, final_explanation = parse_response(judge_response_text, "Final Judge")
            except Exception as e:
                st.error(f"Error generating response from the Judge: {e}")
                final_explanation = f"An error occurred while the judge was deliberating: {e}"

        # --- Display results ---
        # Create a separate expander for each persona
        for res in persona_results:
            persona_display_name = res['name'].replace('_', ' ').title()
            with st.expander(f"{persona_display_name}", expanded=False):
                st.markdown(f"Verdict: **{res['verdict']}**")
                st.markdown(f"Score: {res['score']}")
                st.markdown(f"Explanation: {res['explanation']}")

        st.subheader("Final Verdict from the Judge:")
        if final_verdict in valid_verdicts:
             st.markdown(f"## {final_verdict}")
             if final_verdict == "NTA":
                 st.success("You are likely not the asshole (Final Judgment).")
             elif final_verdict == "YTA":
                 st.error("You might be the asshole (Final Judgment).")
             elif final_verdict == "ESH":
                 st.warning("It seems everyone involved shares some blame (Final Judgment).")
             elif final_verdict == "NAH":
                 st.info("No assholes here, just a complex situation (Final Judgment).")
             elif final_verdict == "INFO":
                 st.info("More information is needed to make a clear judgment (Final Judgment).")

             # Display Score Bar for Final Verdict
             st.subheader("AITA Score (Final Judgment):")
             st.progress(float(final_score) / 100.0)
             st.caption(f"{final_score}% likelihood of being the Asshole (Final Judgment)")

             # Display Final Explanation
             st.subheader("Explanation (Final Judgment):")
             st.markdown(final_explanation)

        else: # Handle cases where final verdict remains "Error"
             st.error("Failed to get a valid final verdict from the Judge.")
             st.subheader("Explanation (Final Judgment):")
             st.markdown(final_explanation)


st.markdown("---")
st.markdown("Note, don't use this with your partner - it will likely piss them off.")
