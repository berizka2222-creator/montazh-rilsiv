// The element library. Each entry: the component, its props schema, and what it is for (Ukrainian, for the skill and the
// reel editor's moments). Add a new element here and it shows up in Studio, in reels (scenes) and in the overlay renders.
import React from "react";
import { z } from "zod";
import { HookTitle, hookTitleSchema } from "./HookTitle";
import { Counter, counterSchema } from "./Counter";
import { ListReveal, listRevealSchema } from "./ListReveal";
import { Marker, markerSchema } from "./Marker";
import { BeforeAfter, beforeAfterSchema } from "./BeforeAfter";
import { Chat, chatSchema } from "./Chat";
import { LowerThird, lowerThirdSchema } from "./LowerThird";
import { CtaEnd, ctaEndSchema } from "./CtaEnd";
import { Bars, barsSchema } from "./Bars";

type Entry = {
  id: string; // composition id
  component: React.FC<any>;
  schema: z.ZodObject<any>;
  ua: string;
  moment: string; // same moments as reel-editor's motion_catalog.json
};

const KEYS = [
  "hook",
  "counter",
  "list",
  "marker",
  "beforeAfter",
  "chat",
  "lowerThird",
  "cta",
  "bars",
] as const;
export type ElementKey = (typeof KEYS)[number];

export const ELEMENTS: Record<ElementKey, Entry> = {
  hook: {
    id: "HookTitle",
    component: HookTitle,
    schema: hookTitleSchema,
    ua: "великий заголовок, слова виринають, акцент рожевим italic",
    moment: "хук / ключова фраза",
  },
  counter: {
    id: "Counter",
    component: Counter,
    schema: counterSchema,
    ua: "цифра рахується до значення, лаймова, з підписом",
    moment: "цифра",
  },
  list: {
    id: "ListReveal",
    component: ListReveal,
    schema: listRevealSchema,
    ua: "список рядками 01/02/03 як у каруселі, з галочками",
    moment: "список / кроки",
  },
  marker: {
    id: "Marker",
    component: Marker,
    schema: markerSchema,
    ua: "фраза, де частину обводить / підсвічує / закреслює рука",
    moment: "хук / ключова фраза",
  },
  beforeAfter: {
    id: "BeforeAfter",
    component: BeforeAfter,
    schema: beforeAfterSchema,
    ua: "було → стало, біль закреслюється рожевим",
    moment: "до / після",
  },
  chat: {
    id: "Chat",
    component: Chat,
    schema: chatSchema,
    ua: "переписка бульбашками з «друкує…»",
    moment: "повідомлення / чат",
  },
  lowerThird: {
    id: "LowerThird",
    component: LowerThird,
    schema: lowerThirdSchema,
    ua: "плашка з іменем і роллю на грудях",
    moment: "ім'я / хто я",
  },
  cta: {
    id: "CtaEnd",
    component: CtaEnd,
    schema: ctaEndSchema,
    ua: "фінальний екран із лаймовою кнопкою-пілюлею",
    moment: "заклик (CTA)",
  },
  bars: {
    id: "Bars",
    component: Bars,
    schema: barsSchema,
    ua: "горизонтальні смуги-порівняння з цифрами",
    moment: "ріст / падіння",
  },
};
