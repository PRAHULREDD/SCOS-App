/**
 * Authentication Logic
 */
document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    
    // Auto-login logic
    const token = localStorage.getItem('token');
    const role = localStorage.getItem('user_role');
    
    if (token && role && window.location.pathname.includes('Login Screen')) {
        redirectBasedOnRole(role);
    }

    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const emailInput = document.getElementById('email').value;
            const passwordInput = document.getElementById('password').value;
            const submitBtn = loginForm.querySelector('button[type="submit"]');
            
            // Set Loading state
            const originalText = submitBtn.innerText;
            submitBtn.innerText = "Signing in...";
            submitBtn.disabled = true;

            try {
                const response = await API.loginUser(emailInput, passwordInput);
                
                // Store state
                localStorage.setItem('token', response.access_token);
                localStorage.setItem('user_role', response.role);
                localStorage.setItem('user_id', response.user_id);
                localStorage.setItem('eco_points', response.eco_points || 0);
                
                showToast("Login successful!", "success");
                
                // Redirect based on role
                setTimeout(() => redirectBasedOnRole(response.role), 1000);
            } catch (error) {
                showToast(error.message, "error");
                submitBtn.innerText = originalText;
                submitBtn.disabled = false;
            }
        });
    }

    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const fullNameInput = document.getElementById('full_name').value;
            const emailInput = document.getElementById('email').value;
            const passwordInput = document.getElementById('password').value;
            const submitBtn = registerForm.querySelector('button[type="submit"]');

            const originalText = submitBtn.innerText;
            submitBtn.innerText = "Registering...";
            submitBtn.disabled = true;

            try {
                await API.registerUser({
                    email: emailInput,
                    password: passwordInput,
                    name: fullNameInput
                });
                showToast("Registration successful! Redirecting to login...", "success");
                setTimeout(() => {
                    window.location.href = '../Login Screen/index.html';
                }, 2000);
            } catch (error) {
                showToast(error.message, "error");
                submitBtn.innerText = originalText;
                submitBtn.disabled = false;
            }
        });
    }
});

function redirectBasedOnRole(role) {
    if (role === 'CITIZEN') {
        window.location.href = '../Citizen Dashboard/index.html';
    } else if (role === 'DRIVER') {
        window.location.href = '../Driver Dashboard/index.html';
    } else if (role === 'ADMIN') {
        // Portal has been consolidated; redirect admin to Role Selection page
        showToast("Admin logged in successfully!", "success");
        setTimeout(() => {
            window.location.href = '../Role Selection/index.html';
        }, 1500);
    } else {
        showToast("Unknown role assignment", "error");
    }
}

// Simple Toast implementation
function showToast(message, type="info") {
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.style.position = 'fixed';
    toast.style.bottom = '20px';
    toast.style.left = '50%';
    toast.style.transform = 'translateX(-50%)';
    toast.style.padding = '12px 24px';
    toast.style.borderRadius = '8px';
    toast.style.color = 'white';
    toast.style.fontWeight = 'bold';
    toast.style.zIndex = '9999';
    toast.style.backgroundColor = type === 'error' ? '#ba1a1a' : '#096430';
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

window.showToast = showToast;
