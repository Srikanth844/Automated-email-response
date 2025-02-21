import pinecone
import openai
import imaplib
import email
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Initialize Pinecone
pinecone.init(api_key="YOUR_PINECONE_API_KEY", environment="YOUR_PINECONE_ENVIRONMENT")
index_name = "email_responses"
pinecone.create_index(index_name, dimension=1536)  # OpenAI's ada-002 model uses 1536 dimensions
index = pinecone.Index(index_name)

# Set up OpenAI
openai.api_key = "YOUR_OPENAI_API_KEY"

# Email configuration
EMAIL_ADDRESS = "your_email@gmail.com"
EMAIL_PASSWORD = "your_email_password"
IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

def embed_text(text):
    response = openai.Embedding.create(input=text, model="text-embedding-ada-002")
    return response['data'][0]['embedding']

def store_email(subject, body, response):
    combined_text = f"Subject: {subject}\nBody: {body}\nResponse: {response}"
    vector = embed_text(combined_text)
    index.upsert([(combined_text, vector)])

def get_similar_responses(query, k=3):
    query_vector = embed_text(query)
    results = index.query(query_vector, top_k=k, include_metadata=True)
    return [result['metadata']['text'] for result in results['matches']]

def generate_response(subject, body):
    query = f"Subject: {subject}\nBody: {body}"
    similar_responses = get_similar_responses(query)
    prompt = f"Based on the following similar email responses, generate a reply for this email:\n\nEmail:\n{query}\n\nSimilar Responses:\n" + "\n".join(similar_responses)
    response = openai.Completion.create(
        engine="text-davinci-002",
        prompt=prompt,
        max_tokens=200
    )
    return response.choices[0].text.strip()

def send_email(to_address, subject, body):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_address
    msg['Subject'] = f"Re: {subject}"
    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    server.send_message(msg)
    server.quit()

def process_email(subject, body, from_address):
    response = generate_response(subject, body)
    send_email(from_address, subject, response)
    store_email(subject, body, response)

def check_emails():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    mail.select("inbox")
    _, message_numbers = mail.search(None, "UNSEEN")
    for num in message_numbers[0].split():
        _, msg = mail.fetch(num, "(RFC822)")
        email_body = msg[0][1]
        email_message = email.message_from_bytes(email_body)
        subject = email_message["subject"]
        from_address = email.utils.parseaddr(email_message["from"])[1]
        
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode()
                    break
        else:
            body = email_message.get_payload(decode=True).decode()
        
        process_email(subject, body, from_address)
    mail.close()
    mail.logout()

def main():
    print("Starting email monitoring system...")
    while True:
        try:
            check_emails()
            print("Checked for new emails. Waiting for 5 minutes before next check.")
            time.sleep(300)  # Check every 5 minutes
        except Exception as e:
            print(f"An error occurred: {e}")
            print("Retrying in 1 minute...")
            time.sleep(60)

if __name__ == "__main__":
    main()