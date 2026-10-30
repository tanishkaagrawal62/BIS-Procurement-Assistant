import { useState } from "react";
import "../Login.css";

function Login({ onBack }) {
  const [showPassword, setShowPassword] = useState(false);

  function handleSubmit(event) {
    event.preventDefault();
    alert("Login is not connected to an authentication service yet.");
  }

  return (
    <main className="login-page">
      <section className="login-brand-panel">
        <button className="login-back" onClick={onBack}>
          ← Back to dashboard preview
        </button>

        <div className="login-brand">
          <span className="login-brand-mark">B</span>
          <span>
            <strong>BIS Assist</strong>
            <small>Procurement intelligence</small>
          </span>
        </div>

        <div className="login-message">
          <span className="login-eyebrow">CONFIDENT PROCUREMENT STARTS HERE</span>
          <h1>Find the right standards for every tender.</h1>
          <p>
            Review tender requirements and explore relevant BIS standards in
            one focused workspace.
          </p>
          <div className="login-note">
            <span>✦</span> Procurement intelligence workspace
          </div>
        </div>

        <div className="login-footer">© 2025 BIS Assist</div>
      </section>

      <section className="login-form-panel">
        <form className="login-form" onSubmit={handleSubmit}>
          <div className="login-mobile-brand">
            <span className="login-brand-mark">B</span>
            <strong>BIS Assist</strong>
          </div>

          <div className="login-eyebrow">WELCOME BACK</div>
          <h2>Sign in to your workspace</h2>
          <p className="login-subtitle">
            Enter your details to continue.
          </p>

          <label htmlFor="email">Work email</label>
          <input
            id="email"
            name="email"
            type="email"
            placeholder="you@company.com"
            autoComplete="email"
            required
          />

          <div className="password-label-row">
            <label htmlFor="password">Password</label>
            <button
              className="forgot-button"
              type="button"
              onClick={() => alert("Password reset will be added later.")}
            >
              Forgot password?
            </button>
          </div>

          <div className="password-input">
            <input
              id="password"
              name="password"
              type={showPassword ? "text" : "password"}
              placeholder="Enter your password"
              autoComplete="current-password"
              required
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>

          <label className="remember-row">
            <input type="checkbox" />
            <span>Keep me signed in</span>
          </label>

          <button className="login-submit" type="submit">
            Sign in <span>→</span>
          </button>

          <p className="signup-prompt">
            New to BIS Assist?{" "}
            <button
              type="button"
              onClick={() => alert("Signup page is coming in a later step.")}
            >
              Create an account
            </button>
          </p>
        </form>
      </section>
    </main>
  );
}

export default Login;
