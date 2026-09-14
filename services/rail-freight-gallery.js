(() => {
  if (document.body.dataset.service !== "rail-freight") return;
  const gallery = document.querySelector(".gallery");
  if (!gallery) return;
  const photos = [
  [
    "6d3c137a-8d89-41b7-97d6-334d5f2255ce",
    "Galvanized steel pipes secured on freight wagons"
  ],
  [
    "def088be-c16e-495a-906d-f008307bbaae",
    "Steel coils secured on flatbed rail wagons"
  ],
  [
    "ec80e09c-4e96-4ca5-b3b6-85e4c9d6cf2f",
    "Heavy steel coils transported by rail"
  ],
  [
    "f2aeeb3c-513e-4f4e-ad4e-8d5664543a61",
    "Steel pipe storage and handling at a rail terminal"
  ],
  [
    "e3e8f14c-512f-4537-a655-8a1268185679",
    "Large steel pipes secured on rail wagons"
  ],
  [
    "fe7d4336-ffd0-44e7-84b6-248993da9e39",
    "Steel coil rail transport beside a mountain terminal"
  ],
  [
    "0b0c4b4f-b4fd-4a3a-92ed-2e2e82e009e8",
    "Crane loading a transformer onto a rail wagon"
  ],
  [
    "0f90c950-aeee-4035-946c-83d83d9645fa",
    "Packed cargo stacked inside a covered freight wagon"
  ],
  [
    "0ff99016-a02c-46c5-8e61-96d37b4add68",
    "Steel pipe freight wagons at a rail yard"
  ],
  [
    "1aa068ed-7d62-4866-94b2-d06ff1ecceed",
    "Railway wheel assemblies transported on a flatbed wagon"
  ],
  [
    "2eac3d27-4194-4943-8e0d-09ff880b86a0",
    "Freight wagons aboard a rail ferry"
  ],
  [
    "3b160cc0-3dde-448d-aabb-9d10145ce432",
    "Road-rail shunting vehicle moving loaded wagons"
  ],
  [
    "3ce398ea-4414-438e-82e8-fbf1ac6ffcab",
    "Forklift loading palletized cargo into a freight wagon"
  ],
  [
    "26eca2b0-95a5-4ea1-a0dc-325f7247d851",
    "Tank wagons lined up at a freight terminal"
  ],
  [
    "144f0cc0-480d-4b96-93b2-34632d172ca1",
    "Rail crane handling heavy industrial equipment"
  ],
  [
    "403f59e9-545f-4ed3-8fec-bc94fe59adb0",
    "Large-diameter steel pipes transported by rail"
  ],
  [
    "19bf5083-8b7f-4bf9-816e-89e4478a38ca",
    "Steel coil staging and rail loading operations"
  ],
  [
    "682d0c23-408a-4a2c-b760-06413965f959",
    "Railway bogies secured on a flatbed wagon"
  ],
  [
    "721ddd58-d364-4e4f-9b0a-90f1d21c50f1",
    "Secured steel pipe loads on freight wagons"
  ],
  [
    "1964ab98-1790-421e-bcbc-9a71d458aef1",
    "Heavy transformers transported on specialized rail wagons"
  ],
  [
    "6627c858-f434-44e6-b729-70ea33666feb",
    "Packaged goods loaded in a covered freight wagon"
  ],
  [
    "d2ec38af-49d8-414d-bf67-4e7698e91415",
    "Oversized transformer transport by rail"
  ],
  [
    "b7f585a3-df17-4293-8849-e91f7fa09257",
    "Transformer secured on a heavy-duty rail wagon"
  ],
  [
    "da4085f0-dd10-4e48-80ab-6fdb72033b93",
    "Steel coil freight train at a logistics terminal"
  ]
];
  for (const [name, alt] of photos) {
    const src = `../assets/gallery/rail-freight/${name}.webp`;
    if ([...gallery.querySelectorAll("[data-full]")].some(item => item.dataset.full === src)) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.photo = name;
    button.dataset.full = src;
    button.setAttribute("aria-label", `Open image: ${alt}`);
    const image = document.createElement("img");
    image.src = src;
    image.alt = alt + " — SAMA Transportations";
    image.loading = "lazy";
    image.decoding = "async";
    image.width = 1536;
    image.height = 1024;
    button.append(image);
    gallery.append(button);
  }
})();
