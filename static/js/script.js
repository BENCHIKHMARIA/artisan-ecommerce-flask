

let currentSlide = 1;
let slideInterval;


function changeSlide(slideNumber) {

    document.querySelectorAll('.hero-slide').forEach(slide => {
        slide.classList.remove('visible');
    });
    
  
    document.querySelectorAll('.hero-dot').forEach(dot => {
        dot.classList.remove('active');
    });
    
    document.getElementById('slide' + slideNumber).classList.add('visible');
    
   
    document.querySelectorAll('.hero-dot')[slideNumber - 1].classList.add('active');
  
    currentSlide = slideNumber;
}

function nextSlide() {
    let next = currentSlide + 1;
    if (next > 3) { 
        next = 1;
    }
    changeSlide(next);
}


function startSlideshow() {
    slideInterval = setInterval(nextSlide, 5000); 
}


document.addEventListener('DOMContentLoaded', function() {
    startSlideshow();
});




document.addEventListener("DOMContentLoaded", function () {
    const slider = document.querySelector('.product-slider');
    const leftBtn = document.querySelector('.left-btn');
    const rightBtn = document.querySelector('.right-btn');
  
    if (slider && leftBtn && rightBtn) {
      leftBtn.addEventListener('click', () => {
        slider.scrollBy({ left: -300, behavior: 'smooth' });
      });
  
      rightBtn.addEventListener('click', () => {
        slider.scrollBy({ left: 300, behavior: 'smooth' });
      });
    }
  });
  




    function toggleUserMenu(event) {
        event.preventDefault();
        const menu = document.getElementById("userMenu");
        menu.style.display = (menu.style.display === "block") ? "none" : "block";
    }

    window.addEventListener("click", function(event) {
        const menu = document.getElementById("userMenu");
        if (!event.target.closest('.user-dropdown')) {
            menu.style.display = "none";
        }
    });






   
function toggleSearchBar(event) {
    event.preventDefault();
    const bar = document.getElementById("searchBar");
    bar.style.display = (bar.style.display === "block") ? "none" : "block";
}

function goToCart(event) {
    event.preventDefault();
    window.location.href = "/panier";  
}


function toggleUserMenu(event) {
    event.preventDefault();
    const menu = document.getElementById("userMenu");
    menu.style.display = (menu.style.display === "block") ? "none" : "block";
}

function performSearch() {
    const value = document.querySelector("#searchBar input").value;
    alert("Recherche de : " + value); 
}















  