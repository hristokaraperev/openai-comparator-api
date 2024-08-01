import streamlit as st
import requests
import pandas as pd

def delete_cv(cv_id):
    response = requests.delete(f"http://127.0.0.1:8000/delete/cv/{cv_id}")
    if response.status_code == 200:
        st.success("CV deleted successfully.")
    else:
        st.error("Error deleting CV.")


def delete_job_description(job_desc_id):
    response = requests.delete(f"http://127.0.0.1:8000/delete/job_description/{job_desc_id}")
    if response.status_code == 200:
        st.success("Job Description deleted successfully.")
    else:
        st.error("Error deleting Job Description.")

st.title("Job Application Management System")

option = st.sidebar.selectbox(
    "Choose an action",
    ("Upload CV", "Upload Job Description", "View CVs", "View Job Descriptions", "Rank CVs")
)

if option == "Upload CV":
    cv_file = st.file_uploader("Upload CV XML", type=["xml"])
    if cv_file is not None:
        files = {"file": cv_file}
        response = requests.post("http://127.0.0.1:8000/upload/cv/", files=files)
        st.write(response.json())

elif option == "Upload Job Description":
    job_desc_file = st.file_uploader("Upload Job Description XML", type=["xml"])
    if job_desc_file is not None:
        files = {"file": job_desc_file}
        response = requests.post("http://127.0.0.1:8000/upload/job_description/", files=files)
        st.write(response.json())

elif option == "View CVs":
    response = requests.get("http://127.0.0.1:8000/cvs/")
    if response.status_code == 200:
        cvs = response.json()["cvs"]
        df_cvs = pd.DataFrame(cvs)
        st.subheader("Uploaded CVs")
        for index, row in df_cvs.iterrows():
            st.write(f"ID: {row['id']} | File Name: {row['file_name']}")
            st.button("Delete", key=row['id'], on_click=delete_cv, args=(row['id'],))

elif option == "View Job Descriptions":
    response = requests.get("http://127.0.0.1:8000/job_descriptions/")
    if response.status_code == 200:
        job_descriptions = response.json()["job_descriptions"]
        df_job_descriptions = pd.DataFrame(job_descriptions)
        st.subheader("Uploaded Job Descriptions")
        for index, row in df_job_descriptions.iterrows():
            st.write(f"ID: {row['id']} | File Name: {row['file_name']}")
            st.button("Delete", key=row['id'], on_click=delete_job_description, args=(row['id'],))

elif option == "Rank CVs":
    st.subheader("Rank CVs against Job Description")
    
    gpt_model = st.selectbox("Select GPT Model", ["gpt-4o-mini", "gpt-4o"])
    
    job_desc_response = requests.get("http://127.0.0.1:8000/job_descriptions/")
    if job_desc_response.status_code == 200:
        job_descriptions = job_desc_response.json()["job_descriptions"]
        job_desc_options = {desc["id"]: desc["file_name"] for desc in job_descriptions}
        selected_job_desc_id = st.selectbox("Select Job Description", list(job_desc_options.keys()), format_func=lambda x: job_desc_options[x])
    
    cv_response = requests.get("http://127.0.0.1:8000/cvs/")
    if cv_response.status_code == 200:
        cvs = cv_response.json()["cvs"]
        cv_options = {cv["id"]: cv["file_name"] for cv in cvs}
        selected_cv_ids = st.multiselect("Select CVs", list(cv_options.keys()), format_func=lambda x: cv_options[x])
    
    if st.button("Rank CVs"):
        payload = {
            "model": gpt_model,
            "cv_ids": selected_cv_ids,
            "job_desc_id": selected_job_desc_id
        }
        response = requests.post("http://127.0.0.1:8000/rank_cvs/", json=payload)
        if response.status_code == 200:
            ranking_result = response.json()["ranking"]
            st.write("Ranking Result:")
            st.write(ranking_result)
        else:
            st.error("Error ranking CVs")
