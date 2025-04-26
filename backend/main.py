# main.py
from fastapi import FastAPI, UploadFile, Form, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io
import os
import httpx
import asyncio
import json
from typing import Optional
from pydantic import BaseModel
import supabase
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AI Database Agent")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase_client = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Groq API client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
groq_headers = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

# Model for chat responses
class ChatResponse(BaseModel):
    response: str

# Function to clean and validate CSV data
def clean_csv_data(df):
    # Basic cleaning operations
    # 1. Check for missing values and replace with mean of the column
    for column in df.select_dtypes(include=['float64', 'int64']).columns:
        if df[column].isnull().any():
            df[column].fillna(df[column].mean(), inplace=True)
    
    # 2. Ensure 'diagnosis' column contains only valid values (M or B)
    if 'diagnosis' in df.columns:
        valid_diagnoses = ['M', 'B']
        df = df[df['diagnosis'].isin(valid_diagnoses)]
    
    # 3. Drop duplicate records based on 'id'
    if 'id' in df.columns:
        df.drop_duplicates(subset=['id'], keep='first', inplace=True)
    
    return df

# Function to upload data to Supabase
async def upload_to_supabase(df):
    try:
        # Convert DataFrame to records (list of dictionaries)
        records = df.to_dict(orient='records')
        
        # Create table if it doesn't exist (first time)
        try:
            # Check if table exists
            supabase_client.table('medical_diagnostics').select('id').limit(1).execute()
        except:
            # Create table schema based on DataFrame columns
            # This is a simplified approach - in production, you would want more control over schema creation
            columns = []
            for col_name, dtype in df.dtypes.items():
                if col_name == 'id':
                    col_type = 'text primary key'
                elif dtype == 'object':
                    col_type = 'text'
                else:
                    col_type = 'float'
                columns.append(f"{col_name} {col_type}")
            
            create_table_query = f"""
            CREATE TABLE IF NOT EXISTS medical_diagnostics (
                {', '.join(columns)}
            );
            """
            # Execute raw SQL query to create table
            supabase_client.table('medical_diagnostics').execute_sql(create_table_query)
        
        # Insert data
        result = supabase_client.table('medical_diagnostics').insert(records).execute()
        return {"success": True, "records_added": len(records)}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Function to process the LLM request through Groq
async def process_llm_request(user_message, file_content=None):
    system_prompt = """
    You are an AI database agent specializing in cleaning medical diagnostic data and interacting with a Supabase database.
    Your main tasks are:
    1. Process and clean CSV files containing medical diagnostic data
    2. Upload cleaned data to the Supabase database
    3. Answer questions about the data and provide insights
    4. Help users query the database
    
    You should be helpful, concise, and informative.
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    if file_content:
        messages.append({
            "role": "user", 
            "content": f"I've uploaded a CSV file with the following preview:\n{file_content}\nPlease process this data."
        })
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GROQ_API_URL,
                headers=groq_headers,
                json={
                    "model": "llama3-70b-8192",
                    "messages": messages,
                    "temperature": 0.5,
                    "max_tokens": 1024
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                response_data = response.json()
                return response_data["choices"][0]["message"]["content"]
            else:
                return f"Error from LLM API: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Failed to process with LLM: {str(e)}"

# Process file and interact with LLM in background
async def process_file_and_llm(file_content, user_message, background_tasks):
    try:
        # Parse CSV content
        df = pd.read_csv(io.StringIO(file_content))
        
        # Clean the data
        cleaned_df = clean_csv_data(df)
        
        # Upload to Supabase
        upload_result = await upload_to_supabase(cleaned_df)
        
        # Generate summary stats
        summary = {
            "row_count": len(cleaned_df),
            "columns": list(cleaned_df.columns),
            "sample_rows": cleaned_df.head(3).to_dict(orient='records')
        }
        
        # Format file content for LLM
        file_preview = f"CSV Sample (first 5 rows):\n{df.head(5).to_string()}"
        
        # Get LLM response
        llm_context = f"""
        User uploaded a CSV file. Here's some information:
        - Original row count: {len(df)}
        - Cleaned row count: {len(cleaned_df)}
        - Upload result: {"Successful" if upload_result.get("success", False) else "Failed"}
        - {file_preview}
        
        User message: {user_message}
        """
        
        llm_response = await process_llm_request(llm_context)
        return llm_response
    except Exception as e:
        return f"Error processing file: {str(e)}"

@app.post("/chat", response_model=ChatResponse)
async def chat(
    background_tasks: BackgroundTasks,
    message: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    try:
        if file:
            # Process the uploaded CSV file
            file_content = await file.read()
            file_content_str = file_content.decode("utf-8")
            
            # Process in background and return immediate acknowledgment
            response_text = await process_file_and_llm(file_content_str, message or "Process this file", background_tasks)
        else:
            # Just process the message with LLM
            response_text = await process_llm_request(message)
        
        return ChatResponse(response=response_text)
    except Exception as e:
        return ChatResponse(response=f"Error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)