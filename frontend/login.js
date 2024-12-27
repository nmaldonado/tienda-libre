// Función para establecer una cookie con un tiempo de expiración
function setCookie(name, value, hours) {
    const date = new Date();
    date.setTime(date.getTime() + (hours * 60 * 60 * 1000)); // Convertir horas a milisegundos
    const expires = "expires=" + date.toUTCString();
    document.cookie = name + "=" + value + ";" + expires + ";path=/";
}

window.onload = () => {
    const navbar = document.getElementById("navbar");
    const footer = document.getElementById("footer");
    const loginContainer = document.getElementById("loginContainer");
    const loginTitle = document.getElementById("loginTitle");

    // Comprobar si el usuario está logueado
    if (document.cookie.includes("logged_in=true")) {
        // Mostrar barra de navegación y footer
        navbar.classList.remove("d-none");
        footer.classList.remove("d-none");

        // Ocultar el formulario de login
        loginContainer.innerHTML = "<h2 class='text-center'></h2>";
        loginTitle.textContent = "Bienvenido nuevamente";
    }
};

document.getElementById("loginForm").addEventListener("submit", async function (e) {
    e.preventDefault();

    const url = 'http://127.0.0.1:5001/login';
    const data = {
        username: document.getElementById("username").value,
        password: document.getElementById("password").value
    };

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            // Login exitoso
            const result = await response.json();
            console.log('Success:', result);

            // Establecer cookie de logged_in válida por 8 horas
            setCookie("logged_in", "true", 8);

            // Mostrar barra de navegación y footer
            document.getElementById("navbar").classList.remove("d-none");
            document.getElementById("footer").classList.remove("d-none");

            // Ocultar el formulario de login
            document.getElementById("loginContainer").innerHTML = "<h1 class='text-center'>Inicio de sesión exitoso</h1>";

            // Actualizar el título
            document.getElementById("loginTitle").textContent = "";

            // Mostrar mensaje de éxito con SweetAlert
            Swal.fire({
                icon: 'success',
                title: '¡Inicio de sesión exitoso!',
                text: 'Has iniciado sesión correctamente.',
                showConfirmButton: false,
                timer: 2000
            });
        } else {
            // Mostrar mensaje de error con SweetAlert
            const errorData = await response.json();
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: errorData.message || "Error desconocido",
                confirmButtonText: 'Aceptar'
            });
        }
    } catch (error) {
        console.error('Error:', error);
        // Mostrar mensaje de error con SweetAlert
        Swal.fire({
            icon: 'error',
            title: 'Error de conexión',
            text: "Ocurrió un error al intentar iniciar sesión. Por favor, inténtalo de nuevo.",
            confirmButtonText: 'Aceptar'
        });
    }
});
