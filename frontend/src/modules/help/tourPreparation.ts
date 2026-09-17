export const TOUR_PREPARATION_EVENT = "calidad:prepare-tour";

export type TourPreparationDetail = {
  tourId: string;
  preparation?: Promise<boolean>;
};

export async function prepareGuidedTour(tourId: string): Promise<boolean> {
  const detail: TourPreparationDetail = { tourId };
  window.dispatchEvent(new CustomEvent(TOUR_PREPARATION_EVENT, { detail }));
  const ready = detail.preparation ? await detail.preparation : true;
  // Esperar a que React haya montado el caso preparado antes de buscar los focos.
  await new Promise<void>((resolve) => window.requestAnimationFrame(() => window.requestAnimationFrame(() => resolve())));
  return ready;
}
