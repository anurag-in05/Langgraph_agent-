## AI-Health-Supervisor-Agent

A multi-agent AI system designed to provide personalized health guidance across fitness, diet, and mental wellness, coordinated by a central **Supervisor Agent**.

This AI assistant helps users improve their well-being by generating:
- 🏋️ Customized workout plans  
- 🥗 Healthy meal suggestions  
- 🧘 Mindfulness and stress-reducing tips  


![My Image](https://github.com/anurag-in05/AI_Health_Supervisor_Agent/blob/43b5fec4b685aca5910e5a93b1b19eab21be8cb7/Architectural_Diagram.png)







### 🛠 Tech Stack
- LangGraph – for building the multi-agent state machine
- LangChain – for Tool orchestration
- Groq (Llama 3.3 70B) – for agent reasoning and responses
- Streamlit – for frontend
- Python – main programming language


### 📦 Installation & Setup

#### 1. Clone the repository
```bash
git clone https://github.com/anurag-in05/AI_Health_Supervisor_Agent.git
cd AI_Health_Supervisor_Agent
```
#### 2. Install dependencies
```bash
pip install -r requirements.txt
```
#### 3. Add your API keys
Copy `.env.example` to `.env` and fill in:
- `GROQ_API_KEY` – from [Groq Console](https://console.groq.com/keys)
- `EXERCISE_API_KEY` – from [API Ninjas](https://api-ninjas.com/profile)
- `DIET_API_KEY` – from [Spoonacular](https://spoonacular.com/food-api/console#Profile)

#### 4. Run the App
```bash
streamlit run main.py
```
