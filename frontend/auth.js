// Función para comprobar si el usuario está logueado
function checkLoginStatus() {
    // Verificar si la cookie 'logged_in=true' está presente
    if (!document.cookie.includes("logged_in=true")) {
        // Si no está logueado, redirigir al index.html
        window.location.href = "index.html";
    }
}
