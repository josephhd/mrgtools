from matplotlib import pyplot
from matplotlib import patches
import numpy

class jdsmith:
    axis = None

    def bilinear_transform(self, z):
        return (z-1)/(z+1)

    def get_admittance_angle(self, R, Y):
        r = (R-1)/(R+1)
        centerx = 1-(1-r)/2
        w = self.bilinear_transform(R + 1j*Y)
        wx = numpy.real(w)
        wy = numpy.imag(w)
        return numpy.rad2deg(numpy.arctan2(wy,wx-centerx))

    def add_constant_admittance(self, linedef, alpha=0.5, linewidth=0.5, **kwargs):
        # linedef should be a list of tuples where the tupe is (Y, startR, stopR)
        # where Y is the admittance line, and R refers to the constnat resistance line
        for l in linedef:
            Y = l[0]
            if numpy.abs(Y) < 1e-10:
                continue

            d1 = self.get_admittance_angle(l[2], Y)
            d2 = self.get_admittance_angle(l[1], Y)

            # print(Y, d1, d2)

            r = 1/Y

            if Y > 0:
                a = patches.Arc((1, r), 2*r, 2*r,  angle=90, theta1=d2, theta2=d1, alpha=alpha, linewidth=linewidth, **kwargs)
            else:
                a = patches.Arc((1, r), 2*r, 2*r,  angle=90, theta2=d2, theta1=d1, alpha=alpha, linewidth=linewidth, **kwargs)

            self.axis.add_patch(a)

    def add_constant_resistance(self, linedef, alpha=0.5, linewidth=0.5, **kwargs):
        # linedef should be a list of tuples where the tupe is (R, startY, stopY)
        # where Y is the admittance line, and R refers to the constnat resistance line
        for l in linedef:
            R = l[0]
            
            if R == 0: 
                continue

            d1 = self.get_admittance_angle(R, l[1])
            d2 = self.get_admittance_angle(R, l[2])
            
            r = (R-1)/(R+1)

            a = patches.Arc((1-(1-r)/2, 0), 1-r, 1-r, angle=0, theta1=d2, theta2=d1, linewidth=linewidth, alpha=alpha, **kwargs)
            self.axis.add_patch(a)

    def add_smith_region(self, resistance_bounds, reactance_bounds, dr=0.1, dx=0.1, alpha=0.5, linewidth=0.5, **kwargs):
        """Generates a Smith chart grid and adds it to the provided axis. resistance_bounds define the limits of each resistance circles in terms of reactance lines, and visa-versa for the reactance bounds. dr and dx specify the steps for the grid for the real and imaginary parts of the impedance."""
        resistances = numpy.arange(reactance_bounds[0], reactance_bounds[1], dr)
        resistances = numpy.append(resistances, reactance_bounds[1])

        reactances = numpy.arange(resistance_bounds[0], resistance_bounds[1], dx)
        reactances = numpy.append(reactances, resistance_bounds[1])

        lines = []
        for R in resistances:
            lines.append((R, resistance_bounds[0], resistance_bounds[1]))
        self.add_constant_resistance(lines, alpha=alpha, linewidth=linewidth, **kwargs)

        
        lines = []
        for Y in reactances:
            lines.append((Y, reactance_bounds[0], reactance_bounds[1]))
        self.add_constant_admittance(lines, alpha=alpha, linewidth=linewidth, **kwargs)

    def add_impedance_labels(self, Z, rule=None, rotation=None, size=8, **kwargs):
        # major resistance lables
        for z in Z:
            w = self.bilinear_transform(z)

            d = numpy.rad2deg(numpy.arctan2(numpy.imag(w), numpy.real(w)))
            text_rot = d

            if rotation != None:
                text_rot = rotation

            if rule == 'real':
                z = numpy.real(z)
            elif(rule == 'imag'):
                z = numpy.imag(z)
        
            if d < 0:
                self.axis.annotate(f" {z:.1f} ", xy=(numpy.real(w), numpy.imag(w)), size=size, rotation_mode='anchor', rotation=180+text_rot, ha='left', va='bottom', **kwargs)
            else:
                self.axis.annotate(f" {z:.1f} ", xy=(numpy.real(w), numpy.imag(w)), size=size, rotation_mode='anchor', rotation=text_rot, ha='right', va='bottom', **kwargs)

    def plot_input_stability(self, s, clip=True, **kwargs):
        s11 = s[:, 0, 0]
        s12 = s[:, 0, 1]
        s21 = s[:, 1, 0]
        s22 = s[:, 1, 1]

        delta = s11*s22 - s12*s21

        c = numpy.conj(s11 - delta*numpy.conj(s22))/(numpy.abs(s11)*numpy.abs(s11) - numpy.abs(delta)*numpy.abs(delta))
        r = numpy.abs(s12*s21/(numpy.abs(s11)*numpy.abs(s11) - numpy.abs(delta)*numpy.abs(delta)))

        # check if the center of the circle is a stable or unstable point
        stable_outside = numpy.abs(s22 + s12*s21*c/(1-s11*c)) > 1

        # for i in range(0, len(c)-1):
        #     c1 = c[i]
        #     r1 = r[i]
        #     s1 = stable_outside[i]

        #     x1 = numpy.real(c1)
        #     y1 = numpy.imag(c1)

        #     c2 = c[i+1]
        #     r2 = r[i+1]
        #     s2 = stable_outside[i+1]

        #     x2 = numpy.real(c2)
        #     y2 = numpy.imag(c2)

        #     if s1 and s2:
        #         if (numpy.abs(c1) - r1) > 1:
        #             continue
        #         betap = numpy.arcsin((r2-r1)/numpy.sqrt(numpy.power(x2-x1, 2) + numpy.power(y2-y1, 2)))
        #         betan = -numpy.arcsin((r2-r1)/numpy.sqrt(numpy.power(x2-x1, 2) + numpy.power(y2-y1, 2)))

        #         gamma = -numpy.arctan2(y2-y1, x2-x1)

        #         alpha = gamma - betap

        #         x3 = x1 + r1*numpy.sin(alpha)
        #         y3 = y1 + r1*numpy.cos(alpha)

        #         x4 = x2 + r2*numpy.sin(alpha)
        #         y4 = y2 + r2*numpy.cos(alpha)

        #         # plot
        #         self.axis.plot([x3, x4], [y3, y4], color='black')
        #         circ = patches.Circle((numpy.real(c1), numpy.imag(c1)), r1, fill=False, linewidth=1, **kwargs)
        #         self.axis.add_patch(circ)

        center_radii = zip(c, r, stable_outside)

        for cs, rs, stable in center_radii:
            if stable:
                if (numpy.abs(cs) - rs) > 1:
                    continue

                # fill the circle as the region to avoid
                circ = patches.Circle((numpy.real(cs), numpy.imag(cs)), rs, fill=False, **kwargs)

            else: 
                if (numpy.abs(numpy.abs(cs) - rs) > 1):
                    continue

                circ = patches.Circle((numpy.real(cs), numpy.imag(cs)), rs, fill=False, **kwargs)

            self.axis.add_patch(circ)
            if clip:
                circ.set_clip_path(self.clip)

    def plot_output_stability(self, s, clip=True, **kwargs):
        s11 = s[:, 0, 0]
        s12 = s[:, 0, 1]
        s21 = s[:, 1, 0]
        s22 = s[:, 1, 1]

        delta = s11*s22 - s12*s21

        c = numpy.conj(s22 - delta*numpy.conj(s11))/(numpy.abs(s22)*numpy.abs(s22) - numpy.abs(delta)*numpy.abs(delta))
        r = numpy.abs(s12*s21/(numpy.abs(s22)*numpy.abs(s22) - numpy.abs(delta)*numpy.abs(delta)))

        # check if the center of the circle is a stable or unstable point
        stable_outside = numpy.abs(s11 + s12*s21*c/(1-s22*c)) > 1

        center_radii = zip(c, r, stable_outside)

        for cl, rl, stable in center_radii:
            # check if this cirle intersects with the smith chart (for cleaner view, and performance improvement)
            if stable:
                if (numpy.abs(cl) - rl) > 1:
                    continue
                # fill the cirlce as the region to avoid
                circ = patches.Circle((numpy.real(cl), numpy.imag(cl)), rl, fill=False, **kwargs)
            else:
                if (numpy.abs(numpy.abs(cl) - rl) > 1):
                    continue
                circ = patches.Circle((numpy.real(cl), numpy.imag(cl)), rl, fill=False, **kwargs)

            self.axis.add_patch(circ)
            if clip:
                circ.set_clip_path(self.clip)


    def plot(self, s, dl=0.1, linewidth=2, arrowscale=16, **kwargs):
        """Plots a REFLECTION COEFFICENT on the chart. Frequency parameter optional. The typical optional arguments to pyplot.plot can be used."""
        p = self.axis.plot(numpy.real(s), numpy.imag(s), linewidth=linewidth, **kwargs)

        # plot arrows based on an accumulated distance
        sum = 0
        for i in range(0, len(s)-1):
            startx = numpy.real(s[i])
            stopx  = numpy.real(s[i+1])
            starty = numpy.imag(s[i])
            stopy  = numpy.imag(s[i+1])

            dist = numpy.sqrt((stopx - startx) * (stopx - startx) + (stopy - starty) * (stopy - starty))

            if sum + dist > dl:
                dx = stopx - startx
                dy = stopy - starty    
                l2norm = numpy.sqrt(dx*dx+dy*dy)
                dx /= l2norm
                dy /= l2norm

                centerx = startx + dx*(dl - sum) 
                centery = starty + dy*(dl - sum) 

                dist -= dl - sum
                sum = dl

                while sum + dist > dl:
                    self.axis.annotate("", 
                            xytext=(
                                centerx, 
                                centery
                                ), 
                            xy=(
                                centerx + 1e-10*dx, 
                                centery + 1e-10*dy
                                ), 
                                arrowprops=dict(arrowstyle='->', mutation_scale=arrowscale, edgecolor=p[0].get_color(), linewidth=linewidth))
                    
                    centerx += dl*dx
                    centery += dl*dy

                    dist -= dl

                sum += dist
            else:
                sum += dist



    def __init__(self, ax, fontsize=8, clip_radius=1):
        """Initializes a given axis as a smith chart."""
        self.axis = ax
        # create the smith chart grid regions, see add_smith_region for details
        self.add_smith_region((-1, 1), (0, 1), dr=0.1, dx=0.1)
        self.add_smith_region((-2, 2), (0, 2), dr=0.2, dx=0.2)
        self.add_smith_region((-5, 5), (0, 5), dr=1, dx=1)
        self.add_smith_region((-10, 10), (0, 10), dr=5, dx=5)

        # finish off the RHS of the smith chart with some final constant resistance circles
        self.add_constant_resistance([(10, -1e6, 1e6)])
        self.add_constant_admittance([(10, 0, 1e6)])
        self.add_constant_admittance([(-10, 0, 1e6)])

        # add the real axis
        self.axis.hlines(0, -1, 1, color='black', linewidth=0.5)

        # finally, add the outer circular boundary
        boundary = patches.Circle((0, 0), 1, edgecolor='black', fill=False, linewidth=1)
        self.axis.add_patch(boundary)

        # major impedance lables
        self.add_impedance_labels(numpy.asarray((0.2+1j*0 ,0.4+1j*0 ,0.6+1j*0 ,0.8+1j*0 ,1+1j*0, 2+1j*0, 3+1j*0, 5+1j*0, 10+1j*0)), rule='real', rotation=0, size=fontsize)
        self.add_impedance_labels(numpy.asarray((0.2*1j ,0.4*1j ,0.6*1j ,0.8*1j, 1*1j, 2*1j, 3*1j, 4*1j, 5*1j, 10*1j)), rule='imag', size=fontsize)
        self.add_impedance_labels(-numpy.asarray((0.2*1j ,0.4*1j ,0.6*1j ,0.8*1j, 1*1j, 2*1j, 3*1j, 4*1j, 5*1j, 10*1j)), rule='imag', size=fontsize)

        # initial boundaries, can be modified later
        self.axis.set_ylim(-1.01, 1.01)
        self.axis.set_xlim(-1.01, 1.01)
        self.axis.set_aspect('equal')
        self.axis.axis(False)

        # create a clip path to hide everything outside of a circle (for things like stability circles)
        self.clip = patches.Circle((0, 0), clip_radius, linewidth=0, fill=False)
        self.axis.add_artist(self.clip)

        # self.axis.set_clip_path(self.clip)




