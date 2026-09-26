(() => {
  const sources=["../assets/services/heavy-equipment-transportation/gallery/01.png?v=20260926-gallery-copy","../assets/services/heavy-equipment-transportation/gallery/02.png?v=20260926-gallery-copy","../assets/services/heavy-equipment-transportation/gallery/03.png?v=20260926-gallery-copy","../assets/services/heavy-equipment-transportation/gallery/04.png?v=20260926-gallery-copy","../assets/services/heavy-equipment-transportation/gallery/05.png?v=20260926-gallery-copy","../assets/services/heavy-equipment-transportation/gallery/06.png?v=20260926-gallery-copy","../assets/services/heavy-equipment-transportation/gallery/07.png?v=20260926-gallery-copy","../assets/services/heavy-equipment-transportation/gallery/08.png?v=20260926-gallery-copy","../assets/services/heavy-equipment-transportation/gallery/09.png?v=20260926-gallery-copy","../assets/services/heavy-equipment-transportation/gallery/10.png?v=20260926-gallery-copy","../assets/services/heavy-equipment-transportation/gallery/11.png?v=20260926-gallery-copy","../assets/services/heavy-equipment-transportation/gallery/12.png?v=20260926-gallery-copy","../assets/services/heavy-equipment-transportation/gallery/13.png?v=20260926-gallery-copy","../assets/services/heavy-equipment-transportation/gallery/14.png?v=20260926-gallery-copy"];
  const gallery=document.querySelector(".projects .gallery");
  if(!gallery) return;
  gallery.classList.add("heavy-equipment-gallery");
  gallery.innerHTML=sources.map((src,index)=>'<button type="button" data-heavy-photo="'+index+'" aria-label="Open heavy equipment gallery image '+(index+1)+'"><img src="'+src+'" alt="Heavy equipment transportation operation '+(index+1)+'" loading="lazy"></button>').join("");

  const lightbox=document.querySelector(".lightbox");
  const photo=lightbox.querySelector("img");
  const replace=(selector)=>{const current=lightbox.querySelector(selector),copy=current.cloneNode(true);current.replaceWith(copy);return copy};
  const closeButton=replace(".close"),previousButton=replace(".previous"),nextButton=replace(".next");
  const count=lightbox.querySelector(".gallery-lightbox-count");
  let active=0;
  let lastTrigger=null;
  let touchStartX=null;
  const show=(index)=>{active=(index+sources.length)%sources.length;photo.src=sources[active];photo.alt="Heavy equipment transportation operation "+(active+1);if(count)count.textContent=String(active+1).padStart(2,"0")+" / "+String(sources.length).padStart(2,"0")};
  const open=(index,trigger)=>{lastTrigger=trigger||null;show(index);lightbox.classList.add("open");lightbox.setAttribute("aria-hidden","false");document.body.classList.add("gallery-modal-open");closeButton.focus()};
  const close=()=>{lightbox.classList.remove("open");lightbox.setAttribute("aria-hidden","true");document.body.classList.remove("gallery-modal-open");if(lastTrigger)lastTrigger.focus()};
  gallery.querySelectorAll("[data-heavy-photo]").forEach(button=>button.addEventListener("click",()=>open(Number(button.dataset.heavyPhoto),button)));
  closeButton.addEventListener("click",close);
  previousButton.addEventListener("click",()=>show(active-1));
  nextButton.addEventListener("click",()=>show(active+1));
  lightbox.addEventListener("click",event=>{if(event.target===lightbox)close()});
  document.addEventListener("keydown",event=>{if(!lightbox.classList.contains("open"))return;if(event.key==="Escape")close();if(event.key==="ArrowLeft")show(active-1);if(event.key==="ArrowRight")show(active+1)});
  lightbox.addEventListener("touchstart",event=>{touchStartX=event.changedTouches[0]?.clientX??null},{passive:true});
  lightbox.addEventListener("touchend",event=>{if(touchStartX===null)return;const endX=event.changedTouches[0]?.clientX??touchStartX;const delta=endX-touchStartX;touchStartX=null;if(Math.abs(delta)<44)return;show(delta>0?active-1:active+1)},{passive:true});
  lightbox.setAttribute("aria-hidden","true");
})();

