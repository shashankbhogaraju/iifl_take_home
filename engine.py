import os
import re
from typing import TypedDict, List, Dict, Any
from bs4 import BeautifulSoup
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

# Fetch the Ollama URL from Docker environment variables
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

class GraphState(TypedDict):
    user_prompt: str
    spec: str
    html_code: str
    errors: List[str]
    iterations: int

def planner_node(state: GraphState) -> Dict[str, Any]:
    print("\n[🧠 Planner] Expanding requirements...")
    model = ChatOllama(model="llama3", base_url=OLLAMA_URL, temperature=0.1)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a lead UI/UX architect. Convert the user's request into a highly detailed text specification for a single-page website.
        CRITICAL ARCHITECTURE RULES:
        1. You MUST always specify a distinct 'Hero / Home' section at the very top. This is the first thing the user sees.
        2. List exact sections required (e.g., Home, About, Projects, Footer).
        3. Specify Tailwind layout structures (e.g., flexbox, grid) and color schemes.
        4. Do not write code. Keep it under 150 words."""),
        ("human", "{user_prompt}")
    ])   
    response = (prompt | model).invoke({"user_prompt": state["user_prompt"]})
    return {"spec": response.content, "iterations": 0}

def coder_node(state: GraphState) -> Dict[str, Any]:
    current_iter = state.get("iterations", 0)
    print(f"\n[💻 Coder] Writing HTML (Iteration {current_iter + 1})...")
    
    model = ChatOllama(model="llama3", base_url=OLLAMA_URL, temperature=0.2) 
    feedback = f"\nFix these errors: {state['errors']}" if state.get("errors") else ""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a Senior Frontend Dev. Write a single-file HTML document using Tailwind CSS via CDN.
        STRICT RULES:
        1. NO HTML COMMENTS OR PLACEHOLDERS. Write actual fake text and use placeholder images.
        2. The 'Home' or 'Hero' section MUST use 'min-h-screen'.
        3. Flex layouts MUST make sense.
        4. Maintain the requested theme.
        5. Output ONLY raw HTML. No markdown, no explanations."""),
        ("human", "Build the UI for this spec:\n{spec}\n{feedback}")
    ])
    response = (prompt | model).invoke({"spec": state["spec"], "feedback": feedback})
    raw_output = response.content
    
    match = re.search(r'(<!DOCTYPE html>.*?</html>|<html>.*?</html>)', raw_output, re.DOTALL | re.IGNORECASE)
    code = match.group(1) if match else raw_output.replace("```html", "").replace("```", "").strip()
        
    return {"html_code": code, "iterations": current_iter + 1}

def qa_node(state: GraphState) -> Dict[str, Any]:
    print("\n[🔍 QA] Checking syntax and layout...")
    errors = []
    html_code = state.get("html_code", "")
    
    soup = BeautifulSoup(html_code, "html.parser")
    if not soup.find("body") or len(soup.find("body").get_text(strip=True)) < 50:
        errors.append("FATAL: The body is empty or lacks visible placeholder text.")

    if not errors:
        print("   -> Syntax passed. Running AI alignment check...")
        critic_model = ChatOllama(model="llama3", base_url=OLLAMA_URL, temperature=0)
        
        critic_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a strict QA Reviewer. Compare the generated HTML against the original Spec. 
            Does the HTML successfully implement the layout, sections, and theme?
            If it is PERFECT, output the exact word 'PASS'.
            If it is missing things, output a bulleted list of what is missing or wrong. DO NOT write code."""),
            ("human", "SPEC:\n{spec}\n\nGENERATED HTML:\n{html_code}")
        ])
        
        critic_response = (critic_prompt | critic_model).invoke({
            "spec": state["spec"],
            "html_code": html_code
        })
        
        evaluation = critic_response.content.strip()
        if "PASS" not in evaluation.upper():
            errors.append(f"ALIGNMENT FAILED: {evaluation}")

    if errors:
        print(f"   -> QA Failed with {len(errors)} errors. Sending back to Coder.")
    else:
        print("   -> QA Passed! Code matches the spec.")

    return {"errors": errors}

def should_continue(state: GraphState):
    if not state.get("errors") or state["iterations"] >= 8:
        return "end"
    return "refine"

workflow = StateGraph(GraphState)
workflow.add_node("planner", planner_node)
workflow.add_node("coder", coder_node)
workflow.add_node("qa", qa_node)

workflow.set_entry_point("planner")
workflow.add_edge("planner", "coder")
workflow.add_edge("coder", "qa")
workflow.add_conditional_edges("qa", should_continue, {"end": END, "refine": "coder"})

app = workflow.compile()

def generate_website(prompt: str, output_path: str):
    print(f"🚀 Starting background generation for: '{prompt}'")
    final_state = app.invoke({"user_prompt": prompt})
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_state.get("html_code", ""))
    print(f"\n✅ Graph finished! Saved to {output_path}")
