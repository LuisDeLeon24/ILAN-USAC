/**
 * Public landing team. The page renders one card per entry, in this order.
 * photo: optional file name inside assets/team/ (served as /team/<file>).
 *        Leave it out to show the initials of name.
 * linkedin: optional http(s) profile URL. The name becomes a link when set.
 */
export type TeamMember = {
  name: string;
  role: string;
  background?: string[];
  photo?: string;
  linkedin?: string;
};

export const team: TeamMember[] = [
  {
    name: "Brandon Boche",
    role: "IEEE Entrepreneurship Ambassador",
    background: ["IEEE Entrepreneurship Ambassador"],
    photo: "brandom-boche.jpg",
  },
  {
    name: "Luis De León",
    role: "Head of Builders Open2",
    background: ["Head of Builders Open2", "Intern at Hualy"],
    photo: "luis-de-leon.jpg",
  },
];
