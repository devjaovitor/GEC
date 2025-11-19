// Animação de fade-in ao carregar página
document.addEventListener("DOMContentLoaded", () => {
    document.body.classList.add("page-loaded");
});

// Transição suave ao navegar para outra página
document.querySelectorAll("a").forEach(link => {
    if (link.getAttribute("target") === "_blank") return;
    if (link.href.startsWith("javascript")) return;

    link.addEventListener("click", function(e) {
        const url = this.href;
        e.preventDefault();

        document.body.classList.add("page-exit");

        setTimeout(() => {
            window.location.href = url;
        }, 180);
    });
});
