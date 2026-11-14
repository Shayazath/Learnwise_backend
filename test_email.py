from app.services.email.email_service import send_email

send_email(
    to_email="shayazath21@gmail.com",
    subject="LearnYah SMTP Test",
    body_text="Your LearnYah email service is working successfully!",
    body_html="""
        <h2>Welcome to LearnYah!</h2>
        <p>Your email service is working successfully.</p>
    """,
)

print("Test email sent successfully!")