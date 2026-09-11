(() => {
  const sources=["../assets/services/heavy-equipment-transportation/gallery/01.png","../assets/services/heavy-equipment-transportation/gallery/02.png","../assets/services/heavy-equipment-transportation/gallery/03.png","../assets/services/heavy-equipment-transportation/gallery/04.png","../assets/services/heavy-equipment-transportation/gallery/05.png","../assets/services/heavy-equipment-transportation/gallery/06.png","../assets/services/heavy-equipment-transportation/gallery/07.png","../assets/services/heavy-equipment-transportation/gallery/08.png","../assets/services/heavy-equipment-transportation/gallery/09.png","../assets/services/heavy-equipment-transportation/gallery/10.png","../assets/services/heavy-equipment-transportation/gallery/11.png","../assets/services/heavy-equipment-transportation/gallery/12.png","../assets/services/heavy-equipment-transportation/gallery/13.png","../assets/services/heavy-equipment-transportation/gallery/14.png"];
  const gallery=document.querySelector(".projects .gallery");
  if(!gallery) return;
  gallery.classList.add("heavy-equipment-gallery");
  gallery.innerHTML=sources.map((src,index)=>'<button type="button" data-heavy-photo="'+index+'" aria-label="Open heavy equipment gallery image '+(index+1)+'"><img src="'+src+'" alt="Heavy equipment transportation operation '+(index+1)+'" loading="lazy"></button>').join("");

  const lightbox=document.querySelector(".lightbox");
  const photo=lightbox.querySelector("img");
  const replace=(selector)=>{const current=lightbox.querySelector(selector),copy=current.cloneNode(true);current.replaceWith(copy);return copy};
  const closeButton=replace(".close"),previousButton=replace(".previous"),nextButton=replace(".next");
  let active=0;
  const show=(index)=>{active=(index+sources.length)%sources.length;photo.src=sources[active];photo.alt="Heavy equipment transportation operation "+(active+1)};
  const open=(index)=>{show(index);lightbox.classList.add("open")};
  const close=()=>lightbox.classList.remove("open");
  gallery.querySelectorAll("[data-heavy-photo]").forEach(button=>button.addEventListener("click",()=>open(Number(button.dataset.heavyPhoto))));
  closeButton.addEventListener("click",close);
  previousButton.addEventListener("click",()=>show(active-1));
  nextButton.addEventListener("click",()=>show(active+1));
  lightbox.addEventListener("click",event=>{if(event.target===lightbox)close()});
  document.addEventListener("keydown",event=>{if(!lightbox.classList.contains("open"))return;if(event.key==="ArrowLeft")show(active-1);if(event.key==="ArrowRight")show(active+1)});
})();