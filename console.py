#!/usr/bin/python3
"""Command interpreter for managing Karabakh Atlas storage objects."""
import cmd
import shlex
from models import storage
from models.region import Region
from models.city import City

classes = {"Region": Region, "City": City}


class KBACommand(cmd.Cmd):
    """Interactive shell to create/inspect/update/delete stored objects."""

    prompt = "(kba) "

    def emptyline(self):
        """Do nothing on an empty input line."""
        pass

    def do_quit(self, arg):
        """Quit the command interpreter."""
        return True

    def do_EOF(self, arg):
        """Handle EOF (Ctrl-D) by exiting the interpreter."""
        print("")
        return True

    def do_create(self, arg):
        """Create a new instance: create <class> [key=value ...]."""
        args = shlex.split(arg)
        if not args:
            print("** class name missing **")
            return
        cls_name = args[0]
        if cls_name not in classes:
            print("** class doesn't exist **")
            return
        kwargs = {}
        for pair in args[1:]:
            if "=" not in pair:
                continue
            key, value = pair.split("=", 1)
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1].replace('\\"', '"').replace("_", " ")
            else:
                try:
                    value = int(value)
                except ValueError:
                    try:
                        value = float(value)
                    except ValueError:
                        continue
            kwargs[key] = value
        obj = classes[cls_name](**kwargs)
        obj.save()
        print(obj.id)

    def do_show(self, arg):
        """Show the string representation of an instance: show <class> <id>."""
        args = shlex.split(arg)
        if not args:
            print("** class name missing **")
            return
        if args[0] not in classes:
            print("** class doesn't exist **")
            return
        if len(args) < 2:
            print("** instance id missing **")
            return
        key = "{}.{}".format(args[0], args[1])
        obj = storage.all().get(key)
        if obj is None:
            print("** no instance found **")
            return
        print(obj)

    def do_destroy(self, arg):
        """Delete an instance: destroy <class> <id>."""
        args = shlex.split(arg)
        if not args:
            print("** class name missing **")
            return
        if args[0] not in classes:
            print("** class doesn't exist **")
            return
        if len(args) < 2:
            print("** instance id missing **")
            return
        key = "{}.{}".format(args[0], args[1])
        obj = storage.all().get(key)
        if obj is None:
            print("** no instance found **")
            return
        obj.delete()
        storage.save()

    def do_all(self, arg):
        """Print all instances, optionally filtered by class: all [class]."""
        args = shlex.split(arg)
        if args and args[0] not in classes:
            print("** class doesn't exist **")
            return
        cls = args[0] if args else None
        print([str(obj) for obj in storage.all(cls).values()])

    def do_count(self, arg):
        """Print the number of instances of a class: count <class>."""
        args = shlex.split(arg)
        if not args or args[0] not in classes:
            print("** class doesn't exist **")
            return
        print(len(storage.all(args[0])))

    def do_update(self, arg):
        """Update an attribute: update <class> <id> <attribute> <value>."""
        args = shlex.split(arg)
        if not args:
            print("** class name missing **")
            return
        if args[0] not in classes:
            print("** class doesn't exist **")
            return
        if len(args) < 2:
            print("** instance id missing **")
            return
        key = "{}.{}".format(args[0], args[1])
        obj = storage.all().get(key)
        if obj is None:
            print("** no instance found **")
            return
        if len(args) < 3:
            print("** attribute name missing **")
            return
        if len(args) < 4:
            print("** value missing **")
            return
        setattr(obj, args[2], args[3])
        obj.save()


if __name__ == "__main__":
    KBACommand().cmdloop()
