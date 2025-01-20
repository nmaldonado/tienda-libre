// Función para establecer una cookie con un tiempo de expiración
// - name: Nombre de la cookie
// - value: Valor de la cookie
// - hours: Tiempo de expiración en horas
function setCookie(name, value, hours) {
    const date = new Date();
    date.setTime(date.getTime() + (hours * 60 * 60 * 1000)); // Convertir horas a milisegundos
    const expires = "expires=" + date.toUTCString();
    document.cookie = name + "=" + value + ";" + expires + ";path=/"; // Establecer cookie en el dominio raíz
}

// Evento que se ejecuta al cargar la página
// - Comprueba si el usuario está logueado verificando la cookie "logged_in"
// - Muestra la barra de navegación y el footer si está logueado
// - Oculta el formulario de login y actualiza el título
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

// Evento que se ejecuta al enviar el formulario de login
// - Captura los datos del formulario
// - Realiza una solicitud POST para autenticar al usuario
// - Si el login es exitoso, establece la cookie "logged_in" y muestra el contenido restringido
document.getElementById("loginForm").addEventListener("submit", async function (e) {
    e.preventDefault(); // Prevenir la recarga de la página

    const url = 'https://panel.tiendalibre.com.uy/api/login'; // URL del backend para autenticación
    const data = {
        username: document.getElementById("username").value, // Captura el usuario
        password: document.getElementById("password").value  // Captura la contraseña
    };

    console.log("Enviando solicitud POST a", url, "con datos", data);
    try {
        // Enviar solicitud POST con Fetch API
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
            // Manejar errores del servidor (códigos 4xx o 5xx)
            const errorData = await response.json();
            throw new Error(errorData.message || "Error desconocido");
        }
    } catch (error) {
        const errorMessage = error.message || "Error desconocido";
        console.error('Error:', error);

        // Mostrar mensaje de error con SweetAlert
        Swal.fire({
            icon: 'error',
            title: 'Error de conexión',
            text: errorMessage,
            confirmButtonText: 'Aceptar'
        });
    }
});

// Cargar la barra de navegación desde el archivo navbar.html
// - Inserta la barra de navegación en el contenedor con id="navbar"
// - Si ocurre un error, lo registra en la consola
document.addEventListener("DOMContentLoaded", function () {
    fetch("navbar.html")
      .then(response => response.text())
      .then(data => {
        document.getElementById("navbar").innerHTML = data; // Inserta la barra de navegación
      })
      .catch(error => console.error("Error cargando la barra de navegación:", error));
});
