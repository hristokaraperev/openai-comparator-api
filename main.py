from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from pydantic import BaseModel
from contextlib import asynccontextmanager
from sqlalchemy import insert, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from database import engine, async_session, metadata
from models import cv_table, job_desc_table
from openai import OpenAI, DefaultHttpxClient
import httpx
import json
from datetime import datetime
import constants
import PyPDF2
from io import BytesIO, StringIO


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield
    # Shutdown ops to be placed here

app = FastAPI(lifespan=lifespan)
#client = OpenAI()
client = OpenAI(
#    base_url="http://10.1.201.30:8000/v1",
#    api_key="-"
)


class RankRequest(BaseModel):
    model: str
    cv_ids: list[int]
    job_desc_id: str


@app.post("/upload/cv/")
async def upload_cv(file: UploadFile = File(...)):
    if file.content_type != "text/plain" and file.content_type != "application/pdf":
        raise HTTPException(400, detail="Invalid document type")
    if file.content_type == "text/plain":
        content = (await file.read()).decode()
    else:
        bytes_content = await file.read()
        bytes_stream = BytesIO(bytes_content)
        pdf_reader = PyPDF2.PdfReader(bytes_stream)

        content = ""
        for page in pdf_reader.pages:
            content += page.extract_text()
    # get the summary
    summary = json.dumps(await generate_skill_summary(content))
    # get CV JSON
    cv_json = json.dumps(await generate_cv_json(content))
    async with async_session() as session:
        async with session.begin():
            stmt = \
                insert(cv_table).values(file_name=file.filename, cv_text=content, cv_summary=summary, cv_json=cv_json)
            await session.execute(stmt)
    return {"filename": file.filename}


@app.post("/upload/job_description/")
async def upload_job_description(file: UploadFile = File(...)):
    content = await file.read()
    async with async_session() as session:
        async with session.begin():
            stmt = insert(job_desc_table).values(file_name=file.filename, content=content.decode())
            await session.execute(stmt)
    return {"filename": file.filename}


@app.get("/cvs/")
async def get_cvs():
    async with async_session() as session:
        result = await session.execute(select(cv_table))
        cvs = result.fetchall()
    return {"cvs": [{"id": row[0], "file_name": row[1]} for row in cvs]}


@app.delete("/delete/cv/{cv_id}")
async def delete_cv(cv_id: int):
    async with async_session() as session:
        async with session.begin():
            stmt = delete(cv_table).where(cv_table.c.id == cv_id)
            await session.execute(stmt)
    return {"message": "CV deleted"}


@app.post("/rank_cvs/")
async def rank_cvs(request: RankRequest):
    async with (async_session() as session):
        cv_result = await session.execute(select(cv_table).where(cv_table.c.id.in_(request.cv_ids)))
        cvs = cv_result.fetchall()
        job_description = request.job_description
        
        cv_texts = "\n-----------------------------------------\n".join(row[4] for row in cvs)
        prompt = f"Rank the following CVs based on their match to а job description. Put ranking score on each CV " \
                 f"between 0 and 100." \
                 f"\nJob description:\n\nJob Description:\n" \
                 f"{job_description}\n\nCVs:\n{cv_texts}"

        completion = client.chat.completions.create(
            model=request.model,
            messages=[
                {"role": "system", "content":
                    "You are a very experienced recruiter, who is going to provide advice about the best candidate "
                    "for a job position."},
                {"role": "user", "content": prompt}
            ]
        )
        
        return {"ranking": completion.choices[0].message}


@app.post("/generate_skill_summary/")
async def generate_skill_summary(request: str = Body(..., media_type='text/plain')):
    cv_text = request
    system_msg = "You are very experienced HR, who can write very good summaries of CV outlining the following " \
                 "things: candidate location (location field, city and country. if unknown just leave empty), " \
                 "overall experience in years (overall_experience field), consulting experience in years " \
                 "(consulting_experience field), summary of the CV (summary field), role category (role_category " \
                 "field), specialty (specialty field), seniority (seniority field), the knowledge domains "\
                 "(knowledge_domains field, comma separated - extract the knowledge domains from the experience " \
                 "including projects and applications developed), soft skills (soft_skills field, comma separated) " \
                 "and tech skills (tech_skills field, comma separated). Include facts which exist in the CV only. " \
                 f"Do not make up things. Current year is {datetime.now().year}."
    user_msg = f"Following is a CV text:\n{cv_text}\nWrite a summary of the above CV and output it in JSON object. "\
               f"Generate only JSON and do not include any additional text outside of the JSON. Use " \
               "```json\n{...}\n``` format."
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]
    )
    msg=completion.choices[0].message.content

    print("Response from model:")
    print(msg)

    #extract the json by looking up ```json {....} ```
    json_start = msg.find("```json") + 8
    json_end = msg.find("```", json_start)

    return json.loads(msg[json_start:json_end])


@app.post("/generate_cv_json")
async def generate_cv_json(cv_text: str = Body(..., media_type='text/plain')):
    system_msg = f"You are assistant, that converts plain text CV to CV JSON object from the different sections of " \
                 f"the CV. For text fields use the text as it is in the CV. Do not modify it. Include facts which " \
                 f"exist in the CV only. Do not make up things. You should use the following example JSON format:" \
                 f"\n{constants.CV_JSON_EXAMPLE}\nAnything not included in the example JSON can be added to " \
                 f"'additional' section in the JSON object. Current year is {datetime.now().year}."
    user_msg = f"Following is a CV text:\n{cv_text}\nGenerate a CV JSON object from the CV. " \
               f"Do not generate any additional text. Use ```json\n{...}\n``` format."
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]
    )
    msg=completion.choices[0].message.content

    print("Response from model:")
    print(msg)

    #extract the json by looking up ```json {....} ```
    json_start = msg.find("```json") + 8
    json_end = msg.find("```", json_start)

    return json.loads(msg[json_start:json_end])

