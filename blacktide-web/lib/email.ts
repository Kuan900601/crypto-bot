export async function sendVerificationEmail(email: string, token: string) {
  const key = process.env.RESEND_API_KEY;
  const base = process.env.NEXTAUTH_URL || "https://app.blacktide.cc";
  if (!key) return;
  const link = `${base}/api/verify-email?token=${token}`;
  await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: "Bearer " + key, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: "noreply@mail.blacktide.cc",
      to: email,
      subject: "【黑潮 BLACKTIDE】驗證您的帳號 Email",
      html: `<div style="font-family:sans-serif;max-width:520px;margin:0 auto;padding:32px 24px;background:#0a0c12;color:#e2e8f0;border-radius:16px">
        <h2 style="color:#e0bf5e;margin-bottom:8px">黑潮 BLACKTIDE</h2>
        <p style="color:#94a3b8;font-size:13px">感謝您註冊！請點擊下方按鈕驗證您的 Email，連結 24 小時內有效。</p>
        <a href="${link}" style="display:inline-block;margin-top:20px;padding:12px 28px;background:#00D4FF;color:#05070A;border-radius:8px;font-weight:700;text-decoration:none;font-size:14px">驗證 Email</a>
        <p style="margin-top:20px;color:#475569;font-size:11px">若您沒有在黑潮平台註冊，請忽略此信。</p>
      </div>`,
    }),
  }).catch(() => {});
}
